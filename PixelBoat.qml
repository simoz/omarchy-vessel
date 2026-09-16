import QtQuick
import qs.Commons

// Top-down boat sprite: the bow points north before the course rotation.
// Integer-sized rectangles keep the artwork sharp without image assets.
Item {
    id: root
    implicitWidth: 18
    implicitHeight: 26
    property color hullColor: Color.accent
    property color deckColor: Color.foreground
    property color windowColor: Color.background
    readonly property var rows: [
        "....h....",
        "...hhh...",
        "..hhhhh..",
        "..hdddh..",
        ".hhdddhh.",
        ".hdddddh.",
        ".hdwwwdh.",
        ".hdwwwdh.",
        ".hdddddh.",
        ".hhdddhh.",
        ".hhdddhh.",
        "..hhhhh..",
        "..hhhhh.."
    ]
    readonly property string pixels: rows.join("")
    readonly property int pixelSize: Math.max(1, Math.floor(Math.min(width / 9, height / 13)))
    Repeater {
        model: root.pixels.length
        Rectangle {
            required property int index
            readonly property string pixel: root.pixels[index]
            x: Math.floor((root.width - 9 * root.pixelSize) / 2) + (index % 9) * root.pixelSize
            y: Math.floor((root.height - 13 * root.pixelSize) / 2) + Math.floor(index / 9) * root.pixelSize
            width: root.pixelSize
            height: root.pixelSize
            visible: pixel !== "."
            color: pixel === "h" ? root.hullColor : pixel === "d" ? root.deckColor : root.windowColor
            antialiasing: false
        }
    }
}
