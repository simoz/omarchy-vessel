import QtQuick
import qs.Commons
import "Model.js" as Model

// Draw only the bundled geography. Both map layers accept the same normalized
// observer coordinates; switching sources must not move any coast or contact.
Canvas {
    id: mapLayer
    property var geography: ({
            available: false,
            polygons: [],
            coastlines: []
        })
    property point offset: Qt.point(0, 0)
    onOffsetChanged: requestPaint()
    property real viewScale: 1
    onViewScaleChanged: requestPaint()
    property color coastColor: Color.accent
    property color landColor: Color.foreground
    onGeographyChanged: requestPaint()
    onCoastColorChanged: requestPaint()
    onLandColorChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    onPaint: {
        var context = getContext("2d");
        context.reset();
        if (!geography.available)
            return;
        var centerPixel = width / 2, radius = Model.radarRadius(width);
        context.save();
        context.beginPath();
        context.arc(centerPixel, centerPixel, radius, 0, Math.PI * 2);
        context.clip();
        var polygons = geography.polygons || [];
        polygons.forEach(function (rings) {
            context.beginPath();
            rings.forEach(function (points) {
                points.forEach(function (p, i) {
                    if (i === 0)
                        context.moveTo(centerPixel + p[0] * radius * viewScale - offset.x, centerPixel + p[1] * radius * viewScale - offset.y);
                    else
                        context.lineTo(centerPixel + p[0] * radius * viewScale - offset.x, centerPixel + p[1] * radius * viewScale - offset.y);
                });
                context.closePath();
            });
            context.fillStyle = landColor;
            context.globalAlpha = 0.09;
            context.fill();
            // Fine hatching gives land a chart-like texture without fixed colors.
            // The polygon's winding also clips the hatch away from inland holes.
            context.save();
            context.clip();
            context.beginPath();
            for (var x = -width; x < width * 2; x += 9) {
                context.moveTo(x, 0);
                context.lineTo(x + width, width);
            }
            context.strokeStyle = landColor;
            context.globalAlpha = 0.045;
            context.lineWidth = 1;
            context.stroke();
            context.restore();
        });
        // Coastlines are a separate dataset, so land partition seams never
        // appear as artificial shores when a viewport crosses a tile edge.
        context.beginPath();
        (geography.coastlines || []).forEach(function (points) {
            points.forEach(function (p, i) {
                if (i === 0)
                    context.moveTo(centerPixel + p[0] * radius * viewScale - offset.x, centerPixel + p[1] * radius * viewScale - offset.y);
                else
                    context.lineTo(centerPixel + p[0] * radius * viewScale - offset.x, centerPixel + p[1] * radius * viewScale - offset.y);
            });
        });
        context.globalAlpha = 0.7;
        context.strokeStyle = coastColor;
        context.lineWidth = 1.2;
        context.lineJoin = "round";
        context.stroke();
        context.restore();
    }
}
