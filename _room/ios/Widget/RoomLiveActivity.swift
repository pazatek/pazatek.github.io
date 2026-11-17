import ActivityKit
import SwiftUI
import WidgetKit

@main
struct RoomWidgetBundle: WidgetBundle {
    var body: some Widget { RoomLiveActivity() }
}

struct RoomLiveActivity: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: RoomAttributes.self) { ctx in
            LockView(s: ctx.state, stale: ctx.isStale)
                .activityBackgroundTint(Color.black.opacity(0.6))
                .activitySystemActionForegroundColor(.white)
        } dynamicIsland: { ctx in
            let s = ctx.state
            return DynamicIsland {
                DynamicIslandExpandedRegion(.leading) { BigTemp(s: s, size: 34).padding(.leading, 6) }
                DynamicIslandExpandedRegion(.trailing) { SideReadings(s: s).padding(.trailing, 6) }
                DynamicIslandExpandedRegion(.bottom) { Footer(s: s, stale: ctx.isStale).padding(.horizontal, 6) }
            } compactLeading: {
                Text(deg(s.temp)).monospacedDigit().foregroundStyle(bandColor(s))
            } compactTrailing: {
                if let c = s.co2 { Text("\(c)").monospacedDigit().foregroundStyle(c >= 1000 ? .orange : .white.opacity(0.7)) }
            } minimal: {
                Text(deg(s.temp, digits: 0)).monospacedDigit().foregroundStyle(bandColor(s))
            }
        }
    }
}
