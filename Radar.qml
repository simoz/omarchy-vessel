import QtQuick
import qs.Commons
import "Model.js" as Model

// Positions are relative to the observer; vessel course controls the symbol orientation.
Item {
    id: root
    property bool scanning: false
    property real markerSize: 12
    property var ships: []
    property var basemap: ({available: false, polygons: [], coastlines: []})
    property real radiusNm: 25
    readonly property bool zoomControlsFocused: zoomInButton.activeFocus || zoomOutButton.activeFocus || centerButton.activeFocus
    signal closeRequested()
    Keys.onEscapePressed: closeRequested()
    property real controlsRightMargin: 0
    property real zoomLevel: 0
    readonly property int maxZoomLevel: 6
    readonly property real zoom: Math.pow(2, zoomLevel)
    readonly property real viewRadiusNm: radiusNm / zoom
    property point viewCenter: Qt.point(0, 0)
    readonly property real chartRadius: Model.radarRadius(width)
    readonly property point centerPixels: Qt.point(viewCenter.x * zoom * chartRadius, viewCenter.y * zoom * chartRadius)
    readonly property bool panned: Math.hypot(viewCenter.x, viewCenter.y) > 0.00001
    readonly property var visibleShips: ships.filter(function(ship) {
        var p = Model.point(ship, root.width, root.viewRadiusNm, root.centerPixels);
        return Model.inView(p, root.width);
    })
    function setCenter(x, y) {
        var p = Model.boundedCenter(x, y, zoom);
        viewCenter = Qt.point(p.x, p.y);
    }
    function pan(dx, dy) {
        setCenter(viewCenter.x + dx * 0.15 / zoom, viewCenter.y + dy * 0.15 / zoom);
    }
    // Recenter only on an explicit list selection, never on each AIS update.
    // Preserve zoom; the coverage constraint keeps the loaded map under the view.
    function focusShip(ship) {
        var center = Model.shipCenter(ship, radiusNm);
        setCenter(center.x, center.y);
    }
    // Restore the initial overview, including when zoomed without any panning.
    function recenter() { zoomLevel = 0; viewCenter = Qt.point(0, 0); }
    onZoomChanged: setCenter(viewCenter.x, viewCenter.y)
    onBasemapChanged: recenter()
    // Keep the zoom local: changing the view must never reconnect the AIS feed.
    function zoomIn() { zoomLevel = Math.min(maxZoomLevel, zoomLevel + 1); }
    function zoomOut() { zoomLevel = Math.max(0, zoomLevel - 1); }
    onRadiusNmChanged: recenter()
    property string selectedMmsi: ""
    signal selected(string mmsi)
    implicitHeight: width
    // Geographic paths use normalized radar coordinates: [0,0] is the observer
    // and a distance of 1 reaches the range ring. Clip all map ink to that ring.
    Canvas {
        id: mapLayer
        anchors.fill: parent
        property var geography: root.basemap
        property point offset: root.centerPixels
        onOffsetChanged: requestPaint()
        property real viewScale: root.zoom
        onViewScaleChanged: requestPaint()
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
            var mid = width / 2, r = root.chartRadius;
            c.save();
            c.beginPath(); c.arc(mid, mid, r, 0, Math.PI * 2); c.clip();
            var polygons = geography.polygons || [];
            polygons.forEach(function(rings) {
                c.beginPath();
                rings.forEach(function(points) {
                    points.forEach(function(p, i) {
                        if (i === 0) c.moveTo(mid + p[0] * r * viewScale - offset.x, mid + p[1] * r * viewScale - offset.y);
                        else c.lineTo(mid + p[0] * r * viewScale - offset.x, mid + p[1] * r * viewScale - offset.y);
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
                    if (i === 0) c.moveTo(mid + p[0] * r * viewScale - offset.x, mid + p[1] * r * viewScale - offset.y);
                    else c.lineTo(mid + p[0] * r * viewScale - offset.x, mid + p[1] * r * viewScale - offset.y);
                });
            });
            c.globalAlpha = 0.7; c.strokeStyle = coastColor; c.lineWidth = 1.2;
            c.lineJoin = "round"; c.stroke(); c.restore();
        }
    }
    // Paint this faint sweep once, then animate the item transform.
    // The sweep stays centered on the viewport, including while the map is panned.
    // Only the sweep texture rotates. Map data, zoom, pan and theme changes
    // repaint their own layers; closing the panel stops the animation.
    Canvas {
        id: sweep
        objectName: "radarSweep"
        anchors.fill: parent
        visible: root.scanning
        property color ink: Color.accent
        onInkChanged: requestPaint()
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onPaint: {
            var c = getContext("2d"); c.reset();
            var mid = width / 2, r = root.chartRadius;
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
        // Property animation survives moving this scene between panel and window;
        // a render-thread Animator can remain attached to the old scene graph.
        NumberAnimation on rotation {
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
            var mid = width / 2, r = root.chartRadius;
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
    Canvas {
        id: cityLayer
        anchors.fill: parent
        property var geography: root.basemap
        property var contacts: root.visibleShips
        property string selection: root.selectedMmsi
        onSelectionChanged: requestPaint()
        property point offset: root.centerPixels
        onOffsetChanged: requestPaint()
        property real viewScale: root.zoom
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
            var c = getContext("2d"); c.reset();
            c.font = "12px monospace";
            var cities = (geography.cities || []).map(function(city) {
                return {name: city.name, x: city.x - root.viewCenter.x, y: city.y - root.viewCenter.y, textWidth: c.measureText(city.name).width};
            });
            // Reserve the visible symbols, not their larger invisible click targets.
            var occupied = [{x: width / 2 - offset.x - 14, y: height / 2 - offset.y - 6, width: 28, height: 32}];
            contacts.forEach(function(ship) {
                var p = Model.point(ship, width, root.viewRadiusNm, root.centerPixels);
                var margin = ship.mmsi === selection ? root.markerSize / 2 + 6 : root.markerSize / 2 + 2;
                occupied.push({x: p.x - margin, y: p.y - margin, width: margin * 2, height: margin * 2});
            });
            var labels = Model.cityLabels(cities, width, viewScale, occupied);
            c.lineJoin = "round"; c.strokeStyle = halo; c.fillStyle = ink;
            labels.forEach(function(label) {
                c.lineWidth = 3; c.strokeText(label.name, label.x, label.y);
                c.fillText(label.name, label.x, label.y);
                c.beginPath(); c.arc(label.dotX, label.dotY, 1.6, 0, Math.PI * 2); c.fill();
            });
        }
    }
    Repeater {
        model: ["N", "E", "S", "W"]
        Text {
            required property int index
            required property string modelData
            x: index === 1 ? root.width - width : index === 3 ? 0 : (root.width - width) / 2
            y: index === 0 ? 0 : index === 2 ? root.height - height : (root.height - height) / 2
            text: modelData; color: Color.muted; font.pixelSize: 12; font.family: "monospace"
        }
    }
    Rectangle { anchors.centerIn: parent; anchors.horizontalCenterOffset: -root.centerPixels.x; anchors.verticalCenterOffset: -root.centerPixels.y; visible: Math.hypot(root.centerPixels.x, root.centerPixels.y) < root.chartRadius - 4; width: 7; height: 7; radius: 4; color: Color.foreground }
    Text { anchors.centerIn: parent; anchors.horizontalCenterOffset: -root.centerPixels.x; anchors.verticalCenterOffset: 17 - root.centerPixels.y; visible: Math.hypot(root.centerPixels.x, 17 - root.centerPixels.y) < root.chartRadius - 16; text: "YOU"; font.pixelSize: 11; color: Color.muted }
    // Stationary contacts are dots; moving contacts use a triangle, oriented by
    // course when available. Unknown speed is a hollow circle.
    ShipModel { id: markerModel; ships: root.ships }
    Repeater {
        model: markerModel
        Item {
            id: target
            required property var ship
            readonly property var modelData: ship
            objectName: "vessel-marker-" + modelData.mmsi
            readonly property var position: Model.point(modelData, root.width, root.viewRadiusNm, root.centerPixels)
            visible: Model.inView(position, root.width)
            readonly property bool chosen: root.selectedMmsi === modelData.mmsi
            readonly property bool hasCourse: typeof modelData.course === "number" && isFinite(modelData.course) && modelData.course >= 0 && modelData.course < 360
            readonly property string motion: Model.motion(modelData)
            readonly property color ink: chosen ? Color.foreground : Color.accent
            x: position.x - 16; y: position.y - 16; width: 32; height: 32
            z: chosen ? 2 : 1
            opacity: modelData.stale ? 0.4 : 1
            Rectangle {
                anchors.centerIn: parent; width: root.markerSize + 10; height: width; radius: width / 2
                color: "transparent"; border.width: 1; border.color: Color.accent
                visible: target.chosen
            }
            Canvas {
                anchors.centerIn: parent; width: root.markerSize; height: width
                visible: target.motion === "moving"
                rotation: target.hasCourse ? target.modelData.course : 0
                property color ink: target.ink
                property color outline: Color.background
                onWidthChanged: requestPaint()
                onHeightChanged: requestPaint()
                onInkChanged: requestPaint()
                onOutlineChanged: requestPaint()
                onPaint: {
                    var c = getContext("2d"); c.reset();
                    c.scale(width / 8, height / 8);
                    c.beginPath(); c.moveTo(4, 0.5); c.lineTo(7.5, 7.5); c.lineTo(0.5, 7.5); c.closePath();
                    c.fillStyle = ink; c.fill();
                    c.lineWidth = 0.6; c.strokeStyle = outline; c.stroke();
                }
            }
            Rectangle {
                anchors.centerIn: parent; width: root.markerSize * 0.75; height: width; radius: width / 2
                visible: target.motion !== "moving"
                color: target.motion === "stationary" ? target.ink : Color.background
                border.width: target.motion === "stationary" ? 0.6 : 1
                border.color: target.motion === "stationary" ? Color.background : target.ink
            }
        }
    }
    // A shared hit test picks the closest contact when generous click targets
    // overlap, rather than letting the last-painted vessel steal the click.
    MouseArea {
        objectName: "mapInteraction"
        anchors.fill: parent
        hoverEnabled: true
        preventStealing: true
        property point pressPoint
        property point pressCenter
        property bool moved: false
        cursorShape: pressed && moved ? Qt.ClosedHandCursor : root.zoomLevel > 0 ? Qt.OpenHandCursor : Qt.ArrowCursor
        onWheel: function(wheel) {
            var dx = wheel.x - width / 2, dy = wheel.y - height / 2;
            if (Math.hypot(dx, dy) > root.chartRadius || wheel.angleDelta.y === 0) {
                wheel.accepted = false; return;
            }
            // Keep the map point under the pointer fixed, within loaded coverage.
            var x = root.viewCenter.x + dx / (root.chartRadius * root.zoom);
            var y = root.viewCenter.y + dy / (root.chartRadius * root.zoom);
            // A standard wheel notch is 120 units: four notches double the zoom.
            // Smaller trackpad deltas produce correspondingly smaller changes.
            root.zoomLevel = Math.max(0, Math.min(root.maxZoomLevel,
                                                root.zoomLevel + wheel.angleDelta.y / 480));
            root.setCenter(x - dx / (root.chartRadius * root.zoom),
                           y - dy / (root.chartRadius * root.zoom));
            if (pressed) {
                pressPoint = Qt.point(wheel.x, wheel.y);
                pressCenter = root.viewCenter;
            }
            wheel.accepted = true;
        }
        onPressed: function(mouse) {
            if (Math.hypot(mouse.x - width / 2, mouse.y - height / 2) > root.chartRadius) {
                mouse.accepted = false; return;
            }
            root.forceActiveFocus();
            pressPoint = Qt.point(mouse.x, mouse.y);
            pressCenter = root.viewCenter;
            moved = false;
        }
        onPositionChanged: function(mouse) {
            if (!pressed) return;
            // A small threshold separates deliberate drags from normal click jitter.
            if (Math.hypot(mouse.x - pressPoint.x, mouse.y - pressPoint.y) > 5) moved = true;
            if (moved) root.setCenter(pressCenter.x - (mouse.x - pressPoint.x) / (root.chartRadius * root.zoom),
                                      pressCenter.y - (mouse.y - pressPoint.y) / (root.chartRadius * root.zoom));
        }
        onClicked: function(mouse) {
            if (moved) return;
            var contact = Model.closestContact(root.visibleShips, mouse.x, mouse.y, root.width, root.viewRadiusNm, root.centerPixels);
            if (contact) root.selected(contact.mmsi);
        }
    }
    Row {
        anchors.right: parent.right
        anchors.rightMargin: root.controlsRightMargin
        anchors.top: parent.top
        spacing: 4
        component ZoomButton: Rectangle {
            property string label
            property bool centerIcon: false
            property string accessibleLabel: label === "+" ? "Zoom in" : "Zoom out"
            property bool available: true
            signal activated()
            width: 32; height: 32; radius: 3
            color: Color.background; border.color: activeFocus ? Color.accent : Color.muted
            opacity: available ? 0.9 : 0.3
            activeFocusOnTab: available
            Accessible.role: Accessible.Button
            Accessible.name: accessibleLabel
            Accessible.onPressAction: if (available) activated()
            Item {
                anchors.centerIn: parent; width: 12; height: 12
                visible: !parent.centerIcon
                Rectangle { anchors.centerIn: parent; width: 12; height: 2; color: Color.foreground }
                Rectangle { anchors.centerIn: parent; width: 2; height: 12; color: Color.foreground; visible: parent.parent.label === "+" }
            }
            // Draw the reticle geometrically so font metrics cannot shift its center.
            Item {
                anchors.centerIn: parent; width: 14; height: 14
                visible: parent.centerIcon
                Rectangle {
                    anchors.centerIn: parent; width: 10; height: 10; radius: 5
                    color: "transparent"; border.width: 1; border.color: Color.foreground
                }
                Rectangle { anchors.centerIn: parent; width: 14; height: 1; color: Color.foreground }
                Rectangle { anchors.centerIn: parent; width: 1; height: 14; color: Color.foreground }
            }
            Keys.onReturnPressed: if (available) activated()
            Keys.onEnterPressed: if (available) activated()
            Keys.onSpacePressed: if (available) activated()
            MouseArea {
                anchors.fill: parent; enabled: parent.available
                cursorShape: Qt.PointingHandCursor
                onClicked: parent.activated()
            }
        }
        ZoomButton { id: centerButton; objectName: "recenter"; label: "⌖"; centerIcon: true; accessibleLabel: "Reset view"; available: root.panned || root.zoomLevel > 0; onActivated: root.recenter() }
        ZoomButton { id: zoomOutButton; objectName: "zoomOut"; label: "−"; available: root.zoomLevel > 0; onActivated: root.zoomOut() }
        ZoomButton { id: zoomInButton; objectName: "zoomIn"; label: "+"; available: root.zoomLevel < root.maxZoomLevel; onActivated: root.zoomIn() }
    }

}
