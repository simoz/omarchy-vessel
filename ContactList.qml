import QtQuick
import qs.Commons
import "Model.js" as Model

// Contacts in receiver order, nearest first. The widget owns selection and
// navigation; rows show the vessel's type color and distance.
ListView {
    id: root
    property var ships: []
    property string selectedMmsi: ""
    property var typeColors: ({})
    property string unit: "nm"
    property string family: "monospace"
    property int textSize: 14
    signal focusRequested(var item)
    signal stepRequested(int step)
    signal revealRequested(var ship)
    signal activated()

    component Label: Text {
        color: Color.foreground; font.family: root.family; font.pixelSize: root.textSize
        textFormat: Text.PlainText
    }

    objectName: "contacts"
    activeFocusOnTab: true
    Accessible.role: Accessible.List
    Accessible.name: "Vessels; use Up and Down to select"
    onActiveFocusChanged: if (activeFocus) root.focusRequested(root)
    Keys.onUpPressed: root.stepRequested(-1)
    Keys.onDownPressed: root.stepRequested(1)
    Keys.onReturnPressed: root.activated()
    Keys.onEnterPressed: root.activated()
    Keys.onSpacePressed: root.activated()
    clip: true
    spacing: 4
    // Keep delegates stable across snapshots; MMSI, not position, is identity.
    model: ShipModel { ships: root.ships }
    Rectangle { anchors.fill: parent; color: "transparent"; border.color: Color.accent; visible: root.activeFocus; z: 2 }
    delegate: Rectangle {
        required property var ship
        readonly property var modelData: ship
        objectName: "vessel-" + modelData.mmsi
        width: ListView.view.width; height: 38
        color: Color.background
        border.width: root.selectedMmsi === modelData.mmsi ? 1 : 0
        border.color: Color.accent
        opacity: modelData.stale ? 0.5 : 1
        Rectangle { anchors.left: parent.left; anchors.leftMargin: 8; anchors.verticalCenter: parent.verticalCenter; width: 8; height: 8; radius: 4; color: root.typeColors[Model.typeGroup(modelData.type)] || Color.accent }
        Label { anchors.left: parent.left; anchors.leftMargin: 24; anchors.verticalCenter: parent.verticalCenter; width: parent.width * 0.65 - 16; elide: Text.ElideRight; text: modelData.name || modelData.mmsi }
        Label { anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter; text: Model.distance(modelData.distance, root.unit); color: Color.accent }
        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.revealRequested(modelData) }
    }
}
