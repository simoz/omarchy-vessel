import QtQuick
import qs.Commons
import "Model.js" as Model

// Positions are relative to the observer; vessel course controls the symbol orientation.
Item {
    id: root
    property bool scanning: false
    property var ships: []
    property var basemap: ({available: false, polygons: [], coastlines: []})
    property real radiusNm: 25
    property string selectedMmsi: ""
    signal selected(string mmsi)
    implicitHeight: width
    // Geographic paths use normalized radar coordinates: [0,0] is the observer
    // and a distance of 1 reaches the range ring. Clip all map ink to that ring.
    Canvas {
        id: mapLayer
        anchors.fill: parent
        property var geography: root.basemap
        property color coastColor: Color.accent
        property color landColor: Color.foreground
        onGeographyChanged: requestPaint()
        onCoastColorChanged: requestPaint()
        onLandColorChanged: requestPaint()
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onPaint: {
            var c = getContext("2d"); c.reset();
            if (!geography.available) return;
            var mid = width / 2, r = mid - 24;
            c.save();
            c.beginPath(); c.arc(mid, mid, r, 0, Math.PI * 2); c.clip();
            var polygons = geography.polygons || [];
            polygons.forEach(function(rings) {
                c.beginPath();
                rings.forEach(function(points) {
                    points.forEach(function(p, i) {
                        if (i === 0) c.moveTo(mid + p[0] * r, mid + p[1] * r);
                        else c.lineTo(mid + p[0] * r, mid + p[1] * r);
                    });
                    c.closePath();
                });
                c.fillStyle = landColor; c.globalAlpha = 0.09; c.fill();
                // Fine hatching gives land a chart-like texture without fixed colors.
                // The polygon's winding also clips the hatch away from inland holes.
                c.save(); c.clip(); c.beginPath();
                for (var x = -width; x < width * 2; x += 9) {
                    c.moveTo(x, 0); c.lineTo(x + width, width);
                }
                c.strokeStyle = landColor; c.globalAlpha = 0.045; c.lineWidth = 1; c.stroke(); c.restore();
            });
            // Coastlines are a separate dataset, so land partition seams never
            // appear as artificial shores when a viewport crosses a tile edge.
            c.beginPath();
            (geography.coastlines || []).forEach(function(points) {
                points.forEach(function(p, i) {
                    if (i === 0) c.moveTo(mid + p[0] * r, mid + p[1] * r);
                    else c.lineTo(mid + p[0] * r, mid + p[1] * r);
                });
            });
            c.globalAlpha = 0.7; c.strokeStyle = coastColor; c.lineWidth = 1.2;
            c.lineJoin = "round"; c.stroke(); c.restore();
        }
    }
    // Paint this faint sweep once, then rotate its texture on the render thread.
    // No timer repaints the map or contacts; closing the panel stops animation.
    Canvas {
        id: sweep
        anchors.fill: parent
        visible: root.scanning
        property color ink: Color.accent
        onInkChanged: requestPaint()
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onPaint: {
            var c = getContext("2d"); c.reset();
            var mid = width / 2, r = Math.max(0, mid - 24);
            c.fillStyle = ink;
            for (var i = 0; i < 20; i++) {
                var start = (-130 + i * 2) * Math.PI / 180;
                c.globalAlpha = 0.008 + i * 0.003;
                c.beginPath(); c.moveTo(mid, mid);
                c.arc(mid, mid, r, start, start + 2.1 * Math.PI / 180);
                c.closePath(); c.fill();
            }
            c.globalAlpha = 0.2; c.strokeStyle = ink; c.lineWidth = 1;
            c.beginPath(); c.moveTo(mid, mid); c.lineTo(mid, mid - r); c.stroke();
        }
        RotationAnimator on rotation {
            from: 0; to: 360; duration: 12000; loops: Animation.Infinite
            running: root.scanning && root.visible
        }
    }
    // Static grid: repaint for geometry or theme changes, not for every incoming position.
    Canvas {
        id: grid
        anchors.fill: parent
        property color ink: Color.accent
        property color muted: Color.muted
        onInkChanged: requestPaint()
        onMutedChanged: requestPaint()
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onPaint: {
            var c = getContext("2d"); c.reset();
            var mid = width / 2, r = mid - 24;
            c.strokeStyle = ink; c.lineWidth = 1; c.globalAlpha = 0.22;
            for (var i = 1; i <= 3; i++) { c.beginPath(); c.arc(mid, mid, r * i / 3, 0, Math.PI * 2); c.stroke(); }
            c.strokeStyle = muted; c.beginPath(); c.moveTo(mid, 24); c.lineTo(mid, width - 24); c.moveTo(24, mid); c.lineTo(width - 24, mid); c.stroke();
            c.globalAlpha = 0.65;
            for (var a = 0; a < 360; a += 10) {
                var rad = a * Math.PI / 180, len = a % 30 === 0 ? 7 : 3;
                c.beginPath(); c.moveTo(mid + Math.sin(rad) * r, mid - Math.cos(rad) * r);
                c.lineTo(mid + Math.sin(rad) * (r - len), mid - Math.cos(rad) * (r - len)); c.stroke();
            }
        }
    }
    Repeater {
        model: ["N", "E", "S", "W"]
        Text {
            required property int index
            required property string modelData
            x: index === 1 ? root.width - width : index === 3 ? 0 : (root.width - width) / 2
            y: index === 0 ? 0 : index === 2 ? root.height - height : (root.height - height) / 2
            text: modelData; color: Color.muted; font.pixelSize: 11; font.family: "monospace"
        }
    }
    Rectangle { anchors.centerIn: parent; width: 7; height: 7; radius: 4; color: Color.foreground }
    Text { anchors.centerIn: parent; anchors.verticalCenterOffset: 17; text: "YOU"; font.pixelSize: 9; color: Color.muted }
    // Use separate items for contacts so each symbol has its own selection hit area.
    Repeater {
        model: root.ships
        Item {
            id: target
            required property var modelData
            readonly property var position: Model.point(modelData, root.width, root.radiusNm)
            x: position.x - 16; y: position.y - 16; width: 32; height: 32
            // Stale positions remain visible but subdued until the receiver expires them.
            opacity: modelData.stale ? 0.4 : 1
            Rectangle { anchors.fill: parent; radius: 16; color: "transparent"; border.color: Color.accent; visible: root.selectedMmsi === target.modelData.mmsi }
            PixelBoat {
                anchors.centerIn: parent
                width: 18; height: 26
                rotation: target.modelData.course === null ? 0 : target.modelData.course
                hullColor: Color.accent
                deckColor: root.selectedMmsi === target.modelData.mmsi ? Color.foreground : Color.muted
            }
            // Unknown course is explicit; an upright sprite alone must not imply northbound travel.
            Text {
                anchors.right: parent.right; anchors.top: parent.top
                text: "?"; visible: target.modelData.course === null
                font.pixelSize: 10; font.bold: true; color: Color.foreground
            }
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.selected(target.modelData.mmsi) }
        }
    }
}
