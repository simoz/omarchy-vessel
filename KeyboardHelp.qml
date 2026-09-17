import QtQuick
import qs.Commons
import "Keyboard.js" as Keyboard

// Modal within the current surface; never opens another receiver or window.
FocusScope {
    id: root
    property string family: "monospace"
    signal closed()
    onVisibleChanged: if (visible) scroll.contentY = 0
    Keys.priority: Keys.BeforeItem
    Keys.onPressed: function(event) {
        event.accepted = true;
        if (event.key === Qt.Key_Escape || event.key === Qt.Key_F1 || event.text === "?") root.closed();
        else if (event.key === Qt.Key_Tab || event.key === Qt.Key_Backtab) { scroll.contentY = 0; closeButton.forceActiveFocus(); }
        else if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter || event.key === Qt.Key_Space) && closeButton.activeFocus) root.closed();
        else if (event.key === Qt.Key_Down || event.key === Qt.Key_PageDown)
            scroll.contentY = Math.min(Math.max(0, scroll.contentHeight - scroll.height), scroll.contentY + (event.key === Qt.Key_Down ? 32 : scroll.height * 0.8));
        else if (event.key === Qt.Key_Up || event.key === Qt.Key_PageUp)
            scroll.contentY = Math.max(0, scroll.contentY - (event.key === Qt.Key_Up ? 32 : scroll.height * 0.8));
    }
    Rectangle { anchors.fill: parent; color: Color.background; opacity: 0.8 }
    MouseArea { anchors.fill: parent; onClicked: root.closed() }
    Rectangle {
        anchors.centerIn: parent
        width: Math.min(parent.width, 720)
        height: Math.min(parent.height, contents.implicitHeight + 32)
        color: Color.background
        border.color: Color.muted
        MouseArea { anchors.fill: parent }
        Flickable {
            id: scroll
            anchors.fill: parent; anchors.margins: 16
            clip: true
            contentHeight: contents.implicitHeight
            boundsBehavior: Flickable.StopAtBounds
            Column {
                id: contents
                width: parent.width; spacing: 18
                Row {
                    width: parent.width
                    Text { width: parent.width - 70; text: "K E Y S"; color: Color.accent; font.family: root.family; font.bold: true; font.pixelSize: 13 }
                    Rectangle {
                        id: closeButton
                        objectName: "closeKeyboardHelp"
                        width: 70; height: 26
                        color: "transparent"; border.color: activeFocus ? Color.accent : Color.muted
                        activeFocusOnTab: true
                        Accessible.role: Accessible.Button
                        Accessible.name: "Close keyboard shortcuts"
                        Accessible.onPressAction: root.closed()
                        Text { anchors.centerIn: parent; text: "ESC ×"; color: Color.foreground; font.family: root.family; font.pixelSize: 11 }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.closed() }
                    }
                }
                Grid {
                    width: parent.width
                    columns: width >= 620 ? 2 : 1
                    columnSpacing: 20; rowSpacing: 10
                    Repeater {
                        model: Keyboard.hints
                        Row {
                            required property var modelData
                            width: (parent.width - (parent.columns - 1) * parent.columnSpacing) / parent.columns
                            spacing: 10
                            Rectangle {
                                width: 126; height: Math.max(24, shortcut.implicitHeight + 8)
                                color: "transparent"; border.color: Color.muted
                                Text { id: shortcut; anchors.centerIn: parent; width: parent.width - 8; text: modelData[0]; wrapMode: Text.WordWrap; color: Color.foreground; font.family: root.family; font.pixelSize: 10 }
                            }
                            Text { width: parent.width - 136; text: modelData[1]; wrapMode: Text.WordWrap; color: Color.foreground; font.family: root.family; font.pixelSize: 11 }
                        }
                    }
                }
                Rectangle { width: parent.width; height: 1; color: Color.muted; opacity: 0.5 }
                Text {
                    width: parent.width; wrapMode: Text.WordWrap
                    text: "In Settings, type normally and use Tab to reach every field and button. Shortcuts apply to the radar view. Escape closes this sheet first."
                    color: Color.muted; font.family: root.family; font.pixelSize: 10
                }
            }
        }
    }
}
