import QtQuick
import qs.Commons
import "Model.js" as Model

// Lay out names after reserving space for the observer and visible contacts.
// Text metrics belong here; Model.cityLabels handles collision and circle bounds.
Canvas {
    id: root
    property var geography: ({
            cities: []
        })
    property var contacts: []
    property string selection: ""
    onSelectionChanged: requestPaint()
    property point offset: Qt.point(0, 0)
    onOffsetChanged: requestPaint()
    property real viewScale: 1
    property point viewCenter: Qt.point(0, 0)
    property real viewRadiusNm: 25
    property real markerSize: 12
    property color ink: Color.muted
    property color halo: Color.background
    onGeographyChanged: requestPaint()
    onContactsChanged: requestPaint()
    onViewScaleChanged: requestPaint()
    onInkChanged: requestPaint()
    onHaloChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    onPaint: {
        var context = getContext("2d");
        context.reset();
        context.font = "12px monospace";
        var cities = (geography.cities || []).map(function (city) {
            return {
                name: city.name,
                x: city.x - root.viewCenter.x,
                y: city.y - root.viewCenter.y,
                textWidth: context.measureText(city.name).width
            };
        });
        // Reserve the visible symbols, not their larger invisible click targets.
        var occupied = [
            {
                x: width / 2 - offset.x - 14,
                y: height / 2 - offset.y - 6,
                width: 28,
                height: 32
            }
        ];
        contacts.forEach(function (ship) {
            var p = Model.point(ship, width, root.viewRadiusNm, root.offset);
            var margin = ship.mmsi === selection ? root.markerSize / 2 + 6 : root.markerSize / 2 + 2;
            occupied.push({
                x: p.x - margin,
                y: p.y - margin,
                width: margin * 2,
                height: margin * 2
            });
        });
        var labels = Model.cityLabels(cities, width, viewScale, occupied);
        context.lineJoin = "round";
        context.strokeStyle = halo;
        context.fillStyle = ink;
        labels.forEach(function (label) {
            context.lineWidth = 3;
            context.strokeText(label.name, label.x, label.y);
            context.fillText(label.name, label.x, label.y);
            context.beginPath();
            context.arc(label.dotX, label.dotY, 1.6, 0, Math.PI * 2);
            context.fill();
        });
    }
}
