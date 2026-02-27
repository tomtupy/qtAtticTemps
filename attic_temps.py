import sys
import math
import os
import psycopg2
from datetime import datetime, timedelta

from PyQt6.QtWidgets import QMainWindow, QApplication, QGraphicsView, QGraphicsScene, QGraphicsTextItem, QWidget, QVBoxLayout, QHBoxLayout
from PyQt6.QtGui import QPolygonF, QBrush, QColor, QPen, QLinearGradient, QPixmap, QPainter, QFont
from PyQt6.QtCore import Qt, QPointF, QTimer, QRectF

class AtticTempsWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Attic Temperatures")
        self.setStyleSheet("background-color: #282c34;")
        self.setFixedSize(220, 270)

        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # House View
        self.house_view = QGraphicsView()
        self.house_scene = QGraphicsScene()
        self.house_view.setScene(self.house_scene)
        self.house_view.setStyleSheet("background-color: #282c34; border: none;")
        layout.addWidget(self.house_view)

        # Gradient Scene (used in memory for color translation)
        self.gradient_scene = QGraphicsScene()

        self.atticTempGradientPixels = None
        self.db_conn = None

        self.connect_to_db()
        self.drawHouse()
        self.atticTempRun()

    def connect_to_db(self):
        try:
            self.db_conn = psycopg2.connect(
                host=os.environ.get("DB_HOST", "[IP_ADDRESS]"),
                database=os.environ.get("DB_NAME", "2phome"),
                user=os.environ.get("USER", "pi"),
                password=os.environ.get("PASS", "<PASSWORD>")
            )
            self.db_conn.autocommit = True
            print("Connected to DB")
        except Exception as e:
            print(f"Failed to connect to DB: {e}")

    def atticTempCreateGradient(self):
        linearGrad = QLinearGradient(0, 0, 150, 0)
        linearGrad.setColorAt(0, QColor(0x62, 0xae, 0xfc))
        linearGrad.setColorAt(0.09, QColor(0, 0xc0, 0xFF))
        linearGrad.setColorAt(0.18, QColor(0, 0xcf, 0xef))
        linearGrad.setColorAt(0.271, QColor(0, 0xda, 0xcd))
        linearGrad.setColorAt(0.361, QColor(0x2c, 0xe0, 0xa1))
        linearGrad.setColorAt(0.451, QColor(0x6d, 0xda, 0x7a))
        linearGrad.setColorAt(0.541, QColor(0x98, 0xd1, 0x57))
        linearGrad.setColorAt(0.631, QColor(0xbe, 0xc6, 0x39))
        linearGrad.setColorAt(0.721, QColor(0xce, 0xb0, 0x1c))
        linearGrad.setColorAt(0.811, QColor(0xdb, 0x97, 0x0a))
        linearGrad.setColorAt(0.903, QColor(0xe4, 0x7d, 0x13))
        linearGrad.setColorAt(1, QColor(0xea, 0x5f, 0x26))

        poly = QPolygonF([QPointF(0, 0), QPointF(150, 0), QPointF(150, 150), QPointF(0, 150)])
        self.gradient_scene.addPolygon(poly, QPen(Qt.PenStyle.NoPen), QBrush(linearGrad))

        paintDevice = QPixmap(150, 150)
        paintDevice.fill(Qt.GlobalColor.transparent)
        painter = QPainter(paintDevice)
        self.gradient_scene.render(painter)
        painter.end()
        self.atticTempGradientPixels = paintDevice.toImage()

    def atticTempRun(self):
        self.atticTempCreateGradient()

        self.timer = QTimer()
        self.timer.setInterval(5000)
        self.timer.timeout.connect(self.poll_db)
        self.timer.start()
        self.poll_db()  # initial call

    def poll_db(self):
        if not self.db_conn:
            return

        print("Querying DB")
        try:
            with self.db_conn.cursor() as cur:
                now = datetime.utcnow()
                lowerTsBoundStr = (now - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
                upperTsBoundStr = (now + timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
                queryStr = f"SELECT DISTINCT ON (sensor_id) sensor_id, time, data, secondary_data, additional_data FROM sensor_data where time > '{lowerTsBoundStr}' and time < '{upperTsBoundStr}' ORDER BY sensor_id, time DESC;"
                
                cur.execute(queryStr)
                rows = cur.fetchall()

                sensorData = {}
                latest_time = None
                for row in rows:
                    sensorId, time, data, secondaryData, _ = row
                    if latest_time is None or time > latest_time:
                        latest_time = time
                    sensorData[sensorId] = {
                        "data": float(data) if data is not None else float('nan'),
                        "secondaryData": float(secondaryData) if secondaryData is not None else float('nan')
                    }
                
                if sensorData:
                    self.house_scene.clear()
                    self.drawHouse()
                    self.drawFillFarSouth(sensorData.get(1238, {}).get("data", float('nan')))
                    self.drawFillSouth(sensorData.get(1239, {}).get("data", float('nan')))
                    self.drawFillFarNorth(sensorData.get(1240, {}).get("data", float('nan')))
                    self.drawFillFarWest(sensorData.get(1235, {}).get("data", float('nan')))
                    self.drawFillWest(sensorData.get(1236, {}).get("data", float('nan')), sensorData.get(1236, {}).get("secondaryData", float('nan')))
                    self.drawFillNorth(sensorData.get(1237, {}).get("data", float('nan')), sensorData.get(1237, {}).get("secondaryData", float('nan')))

                    if latest_time:
                        if latest_time.tzinfo is not None:
                            latest_time_naive = latest_time.replace(tzinfo=None)
                        else:
                            latest_time_naive = latest_time
                        
                        diff = now - latest_time_naive
                        secs = int(diff.total_seconds())
                        if secs < 0:
                            secs = 0
                            
                        if secs < 60:
                            time_str = f"{secs} seconds ago"
                        elif secs < 3600:
                            time_str = f"{secs // 60} minutes ago"
                        else:
                            time_str = f"{secs // 3600} hours ago"
                            
                        font = QFont()
                        font.setPointSize(8)
                        text_item = self.house_scene.addText(time_str, font)
                        text_item.setDefaultTextColor(QColor("#888888"))
                        text_item.setPos(5, 248)

        except Exception as e:
            print(f"DB Query Error: {e}")
            self.db_conn.rollback()

    def getAtticGradientBrush(self, temp):
        try:
            colorAt = self.atticTempGradientPixels.pixel(math.ceil(temp), 1)
            brush = QBrush()
            brush.setStyle(Qt.BrushStyle.SolidPattern)
            brush.setColor(QColor.fromRgba(colorAt))
            return brush
        except Exception:
            return QBrush(QColor(0x57, 0x57, 0x57), Qt.BrushStyle.SolidPattern)

    def drawAtticPolygon(self, points, tempTextPos, humTextPos, temp, humidity):
        poly = QPolygonF([QPointF(x, y) for x, y in points])
        
        brush = QBrush(QColor(0x57, 0x57, 0x57), Qt.BrushStyle.SolidPattern) if math.isnan(temp) else self.getAtticGradientBrush(math.ceil(temp))
        self.house_scene.addPolygon(poly, QPen(Qt.PenStyle.NoPen), brush)

        font = QFont()
        font.setPointSize(9)
        font.setStyle(QFont.Style.StyleNormal)

        if not math.isnan(temp):
            text = self.house_scene.addText(f"{round(temp)}°F", font)
            text.setPos(tempTextPos[0], tempTextPos[1])
            text.setDefaultTextColor(Qt.GlobalColor.black)
        
        if humTextPos and not math.isnan(humidity):
            textHum = self.house_scene.addText(f"{round(humidity)}%", font)
            textHum.setPos(humTextPos[0], humTextPos[1])
            textHum.setDefaultTextColor(Qt.GlobalColor.black)

    def drawFillFarSouth(self, temp):
        pts = [(191, 177), (191, 242), (128, 242), (128, 177)]
        self.drawAtticPolygon(pts, (142, 200), None, temp, float('nan'))

    def drawFillSouth(self, temp):
        pts = [(173, 100), (173, 154), (191, 154), (191, 177), (128, 177), (128, 124)]
        self.drawAtticPolygon(pts, (133, 137), None, temp, float('nan'))

    def drawFillFarNorth(self, temp):
        pts = [(92, 73), (173, 73), (173, 12), (92, 12)]
        self.drawAtticPolygon(pts, (117, 36), None, temp, float('nan'))

    def drawFillFarWest(self, temp):
        pts = [(13, 73), (69, 73), (69, 144), (57, 144), (57, 128), (48, 128), (44, 134), (26, 134), (21, 128), (13, 128), (13, 73)]
        self.drawAtticPolygon(pts, (22, 90), None, temp, float('nan'))

    def drawFillWest(self, temp, humidity):
        pts = [(69, 73), (118, 73), (118, 124), (96, 124), (92, 128), (92, 144), (69, 144)]
        self.drawAtticPolygon(pts, (75, 80), (75, 95), temp, humidity)

    def drawFillNorth(self, temp, humidity):
        pts = [(118, 73), (173, 73), (173, 100), (128, 124), (118, 124)]
        self.drawAtticPolygon(pts, (125, 76), (125, 91), temp, humidity)

    def drawHouse(self):
        pen = QPen(QColor(0, 0, 0))
        pen.setBrush(QBrush(QColor(0, 0, 0)))
        pen.setStyle(Qt.PenStyle.SolidLine)
        pen.setWidth(2)

        lines = [
            (91, 11, 174, 11), (174, 11, 174, 153), (174, 153, 192, 153), (192, 153, 192, 243),
            (192, 243, 127, 243), (127, 243, 127, 125), (127, 125, 97, 125), (97, 125, 93, 129),
            (93, 129, 93, 145), (93, 145, 56, 145), (56, 145, 56, 129), (56, 129, 49, 129),
            (49, 129, 45, 135), (45, 135, 25, 135), (25, 135, 20, 129), (20, 129, 12, 129),
            (12, 129, 12, 72), (12, 72, 91, 72), (91, 72, 91, 11)
        ]
        
        for x1, y1, x2, y2 in lines:
            self.house_scene.addLine(x1, y1, x2, y2, pen)
