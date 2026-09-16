import QtQuick
import qs.Commons

// A compact side-view icon for the bar, separate from the radar contact markers.
Canvas {
    id: root
    implicitWidth: 16
    implicitHeight: 16
    property color ink: Color.foreground
    onInkChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    onPaint: {
        var c = getContext("2d"); c.reset();
        c.scale(width / 16, height / 16);
        c.strokeStyle = ink; c.lineWidth = 1.3; c.lineJoin = "round"; c.lineCap = "round";
        c.beginPath(); c.moveTo(1.5, 8.5); c.lineTo(14.5, 8.5);
        c.lineTo(11.5, 12); c.lineTo(4, 12); c.closePath(); c.stroke();
        c.beginPath(); c.moveTo(5, 8.5); c.lineTo(5, 5); c.lineTo(10, 5);
        c.lineTo(11.5, 8.5); c.moveTo(7, 5); c.lineTo(7, 2); c.stroke();
        c.beginPath(); c.moveTo(1.5, 14); c.lineTo(4, 14.5);
        c.lineTo(7.5, 14); c.lineTo(11, 14.5); c.lineTo(14.5, 14); c.stroke();
    }
}
