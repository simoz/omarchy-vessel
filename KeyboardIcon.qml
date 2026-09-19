import QtQuick
import qs.Commons

// Geometric keys stay legible even when the selected font lacks a keyboard glyph.
Rectangle {
    property color ink: Color.foreground
    implicitWidth: 20
    implicitHeight: 13
    color: "transparent"
    border.color: ink
    radius: 1
    Grid {
        anchors.horizontalCenter: parent.horizontalCenter
        y: 3
        columns: 5
        spacing: 1
        Repeater {
            model: 10
            Rectangle {
                width: 2
                height: 2
                color: ink
            }
        }
    }
    Rectangle {
        anchors.horizontalCenter: parent.horizontalCenter
        y: 10
        width: 10
        height: 1
        color: parent.ink
    }
}
