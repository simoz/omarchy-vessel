import QtQuick
import "Model.js" as Model

ListModel {
    property var ships: []
    // Vessel fields include nullable speed/course and optional source metadata.
    dynamicRoles: true
    onShipsChanged: Model.syncShips(this, ships)
    Component.onCompleted: Model.syncShips(this, ships)
}
