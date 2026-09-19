import QtQuick
import qs.Commons
import "Model.js" as Model

// Projected vectors share the AIS coordinate system; zoom never stretches a bitmap.
Canvas {
    id: layer
    property var geography: ({
            available: false
        })
    // One coordinate unit is the observer's loaded range; offset is already pixels.
    property real viewScale: 1
    property point offset: Qt.point(0, 0)
    property color land: Color.foreground
    property color sea: Color.background
    property color roads: Color.muted
    property color waterway: Color.accent
    onGeographyChanged: requestPaint()
    onViewScaleChanged: requestPaint()
    onOffsetChanged: requestPaint()
    onLandChanged: requestPaint()
    onSeaChanged: requestPaint()
    onRoadsChanged: requestPaint()
    onWaterwayChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    onVisibleChanged: if (visible)
        requestPaint()
    onPaint: {
        var context = getContext("2d");
        context.reset();
        if (!geography.available)
            return;
        var centerPixel = width / 2, radius = Model.radarRadius(width), scale = radius * viewScale;
        function path(points, close) {
            points.forEach(function (p, i) {
                var x = centerPixel + p[0] * scale - offset.x, y = centerPixel + p[1] * scale - offset.y;
                if (i === 0)
                    context.moveTo(x, y);
                else
                    context.lineTo(x, y);
            });
            if (close)
                context.closePath();
        }
        context.save();
        context.beginPath();
        context.arc(centerPixel, centerPixel, radius, 0, Math.PI * 2);
        context.clip();
        context.fillStyle = sea;
        context.fillRect(0, 0, width, height);
        context.fillStyle = land;
        context.globalAlpha = 0.16;
        context.fillRect(0, 0, width, height);
        (geography.tiles || []).forEach(function (tile) {
            // Water uses the background colour; ring winding leaves islands as land.
            context.globalAlpha = 1;
            context.fillStyle = sea;
            context.strokeStyle = sea;
            context.lineWidth = 0.7;
            tile.water.forEach(function (rings) {
                context.beginPath();
                rings.forEach(function (ring) {
                    path(ring, true);
                });
                context.fill();
                // Cover subpixel cracks where independently clipped water polygons meet.
                context.stroke();
            });
        });
        // Draw linework after all water fills so tile arrival/order cannot erase it.
        (geography.tiles || []).forEach(function (tile) {
            context.lineJoin = "round";
            context.globalAlpha = 0.3;
            context.strokeStyle = roads;
            context.lineWidth = 0.8;
            context.beginPath();
            tile.roads.forEach(function (line) {
                path(line, false);
            });
            context.stroke();
            context.globalAlpha = 0.55;
            context.strokeStyle = waterway;
            context.lineWidth = 1;
            context.beginPath();
            tile.waterways.forEach(function (line) {
                path(line, false);
            });
            context.stroke();
        });
        context.restore();
    }
}
