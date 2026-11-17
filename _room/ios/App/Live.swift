import ActivityKit
import Foundation
import Security

private let endpoint = URL(string: "https://hxaftcofwrffwjxtjeoj.supabase.co/functions/v1/room")!

// Hands ActivityKit's push tokens to the room function, which then starts, updates and ends the activity:
//   kind "start"  -> the push-to-start token (lets the server start an activity while the app is closed)
//   kind "update" -> one running activity's token (the server pushes new readings to it)
//   kind "ended"  -> that activity was ended or swiped away
@MainActor
final class Live: ObservableObject {
    static let shared = Live()

    @Published var state: RoomState?
    @Published var log: [String] = []
    @Published var hasKey = Keychain.read() != nil

    #if DEBUG
    private let env = "sandbox"
    #else
    private let env = "production"
    #endif

    private var listening = false
    private var watched = Set<String>()
    // Kept so tokens that arrive before the key is saved are sent once it is.
    private var startToken: String?
    private var updateTokens: [String: String] = [:]

    func listen() {
        guard !listening else { return }
        listening = true
        Task {
            for await data in Activity<RoomAttributes>.pushToStartTokenUpdates {
                startToken = data.hex
                await post(["action": "live_token", "kind": "start", "token": data.hex])
            }
        }
        Task { for await a in Activity<RoomAttributes>.activityUpdates { watch(a) } }
        for a in Activity<RoomAttributes>.activities { watch(a) }
    }

    private func watch(_ a: Activity<RoomAttributes>) {
        guard watched.insert(a.id).inserted else { return }
        Task {
            for await data in a.pushTokenUpdates {
                updateTokens[a.id] = data.hex
                await post(["action": "live_token", "kind": "update", "id": a.id, "token": data.hex])
            }
        }
        Task {
            for await st in a.activityStateUpdates where st == .ended || st == .dismissed {
                updateTokens[a.id] = nil
                await post(["action": "live_token", "kind": "ended", "id": a.id])
                break
            }
        }
    }

    func saveKey(_ key: String) {
        Keychain.save(key.trimmingCharacters(in: .whitespacesAndNewlines))
        hasKey = true
        note("key saved")
        Task {
            if let t = startToken { await post(["action": "live_token", "kind": "start", "token": t]) }
            for (id, t) in updateTokens { await post(["action": "live_token", "kind": "update", "id": id, "token": t]) }
            await refresh()
        }
    }

    // The same content the server pushes, so the app shows exactly what the lock screen will.
    func refresh() async {
        guard let data = await post(["action": "live_state"]) else { return }
        state = try? JSONDecoder().decode(RoomState.self, from: data)
    }

    func startNow() async {
        guard Activity<RoomAttributes>.activities.isEmpty else { note("already running"); return }
        guard ActivityAuthorizationInfo().areActivitiesEnabled else { note("Live Activities are off in Settings"); return }
        await refresh()
        guard let s = state else { note("no reading to show"); return }
        do {
            let a = try Activity.request(attributes: RoomAttributes(), content: .init(state: s, staleDate: Date().addingTimeInterval(600)), pushType: .token)
            note("started \(a.id.prefix(8))")
        } catch {
            note("start failed: \(error.localizedDescription)")
        }
    }

    func endAll() async {
        for a in Activity<RoomAttributes>.activities { await a.end(nil, dismissalPolicy: .immediate) }
        note("ended")
    }

    @discardableResult
    private func post(_ body: [String: String]) async -> Data? {
        guard let key = Keychain.read() else { note("no key yet"); return nil }
        var b = body
        b["env"] = env
        var req = URLRequest(url: endpoint)
        req.httpMethod = "POST"
        req.setValue(key, forHTTPHeaderField: "x-room-key")
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try? JSONSerialization.data(withJSONObject: b)
        let what = [body["action"], body["kind"]].compactMap { $0 }.joined(separator: " ")
        do {
            let (data, res) = try await URLSession.shared.data(for: req)
            let code = (res as? HTTPURLResponse)?.statusCode ?? 0
            if body["action"] != "live_state" || code != 200 { note("\(what): \(code)") }
            return code == 200 ? data : nil
        } catch {
            note("\(what) failed: \(error.localizedDescription)")
            return nil
        }
    }

    private func note(_ s: String) {
        let t = Date().formatted(date: .omitted, time: .standard)
        log.append("\(t) \(s)")
        if log.count > 40 { log.removeFirst(log.count - 40) }
    }
}

extension Data {
    var hex: String { map { String(format: "%02x", $0) }.joined() }
}

// The room key lives in the Keychain, readable after first unlock so background launches can use it.
enum Keychain {
    private static func query() -> [String: Any] {
        [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: "room", kSecAttrAccount as String: "x-room-key"]
    }

    static func read() -> String? {
        var q = query()
        q[kSecReturnData as String] = true
        q[kSecMatchLimit as String] = kSecMatchLimitOne
        var out: AnyObject?
        guard SecItemCopyMatching(q as CFDictionary, &out) == errSecSuccess, let d = out as? Data else { return nil }
        return String(data: d, encoding: .utf8)
    }

    static func save(_ v: String) {
        SecItemDelete(query() as CFDictionary)
        var a = query()
        a[kSecValueData as String] = Data(v.utf8)
        a[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlock
        SecItemAdd(a as CFDictionary, nil)
    }
}
