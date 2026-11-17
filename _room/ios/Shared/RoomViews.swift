import SwiftUI

// Views shared by the Live Activity (widget extension) and the app's preview of it.
typealias RoomState = RoomAttributes.ContentState

func deg(_ f: Double, digits: Int = 1) -> String { String(format: digits == 0 ? "%.0f°" : "%.1f°", f) }

// White inside the comfort band, orange above it, blue below it.
func bandColor(_ s: RoomState) -> Color { s.temp > s.hi ? .orange : s.temp < s.lo ? .cyan : .white }

struct BigTemp: View {
    let s: RoomState
    var size: CGFloat = 40
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text(s.label.uppercased()).font(.caption2.weight(.semibold)).foregroundStyle(.white.opacity(0.6))
            Text(deg(s.temp)).font(.system(size: size, weight: .semibold, design: .rounded)).monospacedDigit().foregroundStyle(bandColor(s))
                .contentTransition(.numericText())
        }
    }
}

struct SideReadings: View {
    let s: RoomState
    var body: some View {
        Grid(alignment: .trailing, horizontalSpacing: 10, verticalSpacing: 2) {
            if let b = s.bed { row("Bed", deg(b)) }
            if let o = s.out { row("Out", deg(o, digits: 0)) }
            if let c = s.co2 { row("CO₂", "\(c)", warn: c >= 1000) }
            if let h = s.hum { row("Hum", "\(h)%") }
        }
        .font(.subheadline)
    }

    @ViewBuilder func row(_ k: String, _ v: String, warn: Bool = false) -> some View {
        GridRow {
            Text(k).foregroundStyle(.white.opacity(0.6))
            Text(v).monospacedDigit().foregroundStyle(warn ? .orange : .white)
        }
    }
}

struct Footer: View {
    let s: RoomState
    let stale: Bool
    var body: some View {
        HStack(spacing: 4) {
            Text(stale ? "No new reading" : s.what).lineLimit(1)
            Spacer(minLength: 8)
            Text(Date(timeIntervalSince1970: s.ts), style: .timer).monospacedDigit().multilineTextAlignment(.trailing).frame(maxWidth: 52)
            Text("ago")
        }
        .font(.footnote)
        .foregroundStyle(.white.opacity(0.75))
    }
}

struct LockView: View {
    let s: RoomState
    let stale: Bool
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .center) {
                BigTemp(s: s)
                Spacer()
                SideReadings(s: s)
            }
            Footer(s: s, stale: stale)
        }
        .padding(16)
        .opacity(stale ? 0.6 : 1)
    }
}
