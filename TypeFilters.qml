import QtQuick
import qs.Commons
import "Model.js" as Model

// Type filters double as the color legend; keys 1–6 toggle them too. Equal
// cells keep labels and counts aligned: one row of six when it fits,
// otherwise two rows of three.
Grid {
    id: root
    property var hiddenTypes: ({})
    property var typeColors: ({})
    property var typeCounts: ({})
    property string family: "monospace"
    property int smallTextSize: 11
    signal toggled(string key)
    signal focusRequested(var item)
    signal closeRequested()

    component Label: Text {
        color: Color.foreground; font.family: root.family; font.pixelSize: root.smallTextSize
        textFormat: Text.PlainText
    }

    objectName: "typeFilters"
    spacing: 6
    columns: width >= 660 ? 6 : 3
    readonly property real cellWidth: (width - (columns - 1) * spacing) / columns
    Repeater {
        model: Model.typeGroups
        Rectangle {
            id: chip
            required property var modelData
            required property int index
            readonly property bool shown: !root.hiddenTypes[modelData.key]
            readonly property color ink: root.typeColors[modelData.key] || Color.accent
            objectName: "typeFilter-" + modelData.key
            width: root.cellWidth; height: 26; radius: 3
            color: shown ? Qt.alpha(ink, 0.12) : "transparent"
            border.width: 1
            border.color: activeFocus ? Color.foreground : shown ? Qt.alpha(ink, 0.7) : Qt.alpha(Color.muted, 0.5)
            activeFocusOnTab: true
            Accessible.role: Accessible.CheckBox
            Accessible.name: "Show " + modelData.label.toLowerCase() + " vessels, key " + (index + 1)
            Accessible.checkable: true
            Accessible.checked: shown
            Accessible.onPressAction: root.toggled(modelData.key)
            onActiveFocusChanged: if (activeFocus) root.focusRequested(chip)
            Keys.onReturnPressed: root.toggled(modelData.key)
            Keys.onEnterPressed: root.toggled(modelData.key)
            Keys.onSpacePressed: root.toggled(modelData.key)
            Keys.onEscapePressed: root.closeRequested()
            Rectangle {
                id: chipDot
                anchors.left: parent.left; anchors.leftMargin: 8
                anchors.verticalCenter: parent.verticalCenter
                width: 8; height: 8; radius: 4
                color: chip.shown ? chip.ink : "transparent"
                border.width: 1; border.color: chip.shown ? chip.ink : Color.muted
            }
            Label {
                anchors.left: chipDot.right; anchors.leftMargin: 6
                anchors.right: chipCount.left; anchors.rightMargin: 4
                anchors.verticalCenter: parent.verticalCenter
                text: chip.modelData.label
                elide: Text.ElideRight
                font.strikeout: !chip.shown
                color: chip.shown ? Color.foreground : Color.muted
            }
            Label {
                id: chipCount
                anchors.right: parent.right; anchors.rightMargin: 8
                anchors.verticalCenter: parent.verticalCenter
                text: root.typeCounts[chip.modelData.key] || 0
                color: chip.shown ? chip.ink : Color.muted
            }
            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: root.toggled(chip.modelData.key)
            }
        }
    }
}
