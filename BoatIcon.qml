import QtQuick
import qs.Commons

// A rounded front-view ship for the bar, separate from radar contact markers.
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
        c.scale(width / 24, height / 24);
        c.strokeStyle = ink; c.lineWidth = 1.9;
        c.lineJoin = "round"; c.lineCap = "round";
        c.beginPath();
        c.moveTo(8, 10); c.lineTo(8, 5.5); c.lineTo(16, 5.5); c.lineTo(16, 10);
        c.moveTo(10, 5.5); c.lineTo(10, 3); c.lineTo(14, 3); c.lineTo(14, 5.5);
        c.stroke();
        c.beginPath();
        c.moveTo(4, 12); c.lineTo(12, 9); c.lineTo(20, 12);
        c.lineTo(17.5, 18); c.lineTo(12, 21); c.lineTo(6.5, 18);
        c.closePath(); c.stroke();
        c.beginPath(); c.moveTo(12, 9); c.lineTo(12, 21); c.stroke();
    }
}
