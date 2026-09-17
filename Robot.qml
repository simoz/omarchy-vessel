import QtQuick
import qs.Commons

// Render the sprite with theme-bound rectangles so palette changes apply immediately.
Item {
    id: root
    implicitWidth: 112
    implicitHeight: 112
    property bool awake: true
    property bool live: false
    property bool eyesLit: false
    readonly property bool animated: visible && awake
    readonly property bool flashing: animated && live
    onFlashingChanged: eyesLit = flashing
    property real bob: 0
    onAnimatedChanged: {
        if (!animated) bob = 0;
    }
    // Sprite legend: dot = transparent, a = accent outline, f = body, b = eyes.
    readonly property var pixels: [
        "........aa......", ".........a......", "....aaaaaaaa....",
        "...affffffffa...", "...afbbffbbfa...", "...affffffffa...",
        "....aaaaaaaa....", ".......aa.......", "...aaaaaaaaaa...",
        "..aafffffffaaa..", "..aaffaffffaa...", "..aafffffffaa...",
        "....aaaaaaaa....", ".....aa..aa.....", "....aaa..aaa...."
    ]
    readonly property string sprite: pixels.join("")
    // Flatten the rows into a pixel grid and scale it to the requested component size.
    Repeater {
        model: root.sprite.length
        Rectangle {
            required property int index
            readonly property string pixel: root.sprite[index]
            x: (index % 16) * root.width / 16
            y: Math.floor(index / 16) * root.height / 16 + root.bob
                + (pixel === "b" && (!root.awake) ? root.height / 32 : 0)
            width: Math.ceil(root.width / 16)
            height: pixel === "b" && (!root.awake) ? 1 : Math.ceil(root.height / 16)
            visible: pixel !== "."
            color: pixel === "a" ? Color.accent : pixel === "b" ? (!root.awake ? Color.muted : root.eyesLit ? Color.accent : Color.background) : Color.foreground
        }
    }
    // A gentle bob makes activity visible without distracting from the chart.
    // Animate a QML property so moving between windows cannot strand an animator.
    SequentialAnimation on bob {
        running: root.animated
        loops: Animation.Infinite
        NumberAnimation { from: 0; to: -2; duration: 1000; easing.type: Easing.InOutSine }
        NumberAnimation { from: -2; to: 0; duration: 1000; easing.type: Easing.InOutSine }
        PauseAnimation { duration: 900 }
    }
    // Live reception lights both eyes in a steady on/off rhythm. Stopping or
    // hiding the robot resets the lights immediately and stops the timer.
    Timer {
        interval: 900
        running: root.flashing
        repeat: true
        onTriggered: root.eyesLit = !root.eyesLit
    }
}
