import QtQuick
import qs.Commons

// Render the sprite with theme-bound rectangles so palette changes apply immediately.
Item {
    id: root
    implicitWidth: 112
    implicitHeight: 112
    property bool awake: true
    property bool blink: false
    // Sprite legend: dot = transparent, a = accent outline, f = body, b = eyes.
    readonly property var pixels: [
        "........aa......", ".........a......", "....aaaaaaaa....",
        "...affffffffa...", "...afbbffbbfa...", "...affffffffa...",
        "....aaaaaaaa....", ".......aa.......", "...aaaaaaaaaa...",
        "..aafffffffaaa..", "..aaffaffffaa...", "..aafffffffaa...",
        "....aaaaaaaa....", ".....aa..aa.....", "....aaa..aaa...."
    ]
    // Flatten the rows into a pixel grid and scale it to the requested component size.
    Repeater {
        model: root.pixels.join("").length
        Rectangle {
            required property int index
            readonly property string pixel: root.pixels.join("")[index]
            x: (index % 16) * root.width / 16
            y: Math.floor(index / 16) * root.height / 16
            width: Math.ceil(root.width / 16)
            height: Math.ceil(root.height / 16)
            visible: pixel !== "."
            color: pixel === "a" ? Color.accent : pixel === "b" ? (root.blink || !root.awake ? Color.muted : Color.background) : Color.foreground
        }
    }
    // Blink only while the robot is visible and awake; keep the rest of the sprite still.
    Timer { interval: 4800; running: root.visible && root.awake; repeat: true; onTriggered: { root.blink = true; blinkEnd.restart(); } }
    Timer { id: blinkEnd; interval: 140; onTriggered: root.blink = false }
}
