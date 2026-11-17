import ActivityKit
import Foundation

// One Live Activity: the room's readings on the lock screen and in the Dynamic Island.
// The server (functions/room.ts, liveState) builds ContentState; the JSON keys must match these names.
struct RoomAttributes: ActivityAttributes {
    struct ContentState: Codable, Hashable {
        var label: String   // which sensor the big number is: "Desk" while awake, "Bed" asleep
        var temp: Double    // °F
        var lo: Double      // comfort band for that mode, °F
        var hi: Double
        var bed: Double?    // °F, only when the big number is the desk
        var out: Double?    // °F outside
        var co2: Int?       // ppm
        var hum: Int?       // %
        var what: String    // what the room should be set to, e.g. "Window ¼ · door closed · fan off"
        var ts: Double      // reading time, unix seconds
    }
}
