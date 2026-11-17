import ActivityKit
import SwiftUI

@main
struct RoomCoachApp: App {
    @StateObject private var live = Live.shared
    // Runs on every launch, including the background launch iOS does after the server starts an activity by push,
    // so the new activity's update token reaches the server.
    init() { Live.shared.listen() }
    var body: some Scene { WindowGroup { ContentView().environmentObject(live) } }
}

struct ContentView: View {
    @EnvironmentObject var live: Live
    @State private var draft = ""

    var body: some View {
        NavigationStack {
            List {
                if let s = live.state {
                    Section {
                        LockView(s: s, stale: Date().timeIntervalSince1970 - s.ts > 600)
                            .background(Color.black.opacity(0.85), in: RoundedRectangle(cornerRadius: 20))
                            .listRowInsets(EdgeInsets())
                            .listRowBackground(Color.clear)
                    }
                }
                Section {
                    Button("Start now") { Task { await live.startNow() } }
                    Button("End", role: .destructive) { Task { await live.endAll() } }
                } header: {
                    Text("Live Activity")
                } footer: {
                    Text("Starts by itself when you're home and awake, and ends when you go to sleep or leave.")
                }
                Section("App key") {
                    SecureField(live.hasKey ? "Saved" : "Paste the room key", text: $draft)
                        .textInputAutocapitalization(.never).autocorrectionDisabled()
                    Button("Save") { live.saveKey(draft); draft = "" }.disabled(draft.count < 16)
                }
                Section {
                    Link("Open the room view", destination: URL(string: "https://piotrzatek.com/room/")!)
                }
                Section("Log") {
                    ForEach(Array(live.log.enumerated().reversed()), id: \.offset) { Text($0.element).font(.caption.monospaced()) }
                }
            }
            .navigationTitle("Room")
            .refreshable { await live.refresh() }
            .task { await live.refresh() }
        }
    }
}
