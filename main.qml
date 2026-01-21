/*
 * Main Interface v4.1 (Big Start Button)
 * - Start Button: Increased size and visibility
 */

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import QtQuick.Controls.Material

ApplicationWindow {
    id: window
    title: "Thermal Command Interface"
    visible: true
    width: 1280
    height: 800
    color: "#121212"

    Material.theme: Material.Dark
    Material.accent: Material.LightGreen

    Component.onCompleted: window.showMaximized()

    RowLayout {
        anchors.fill: parent
        spacing: 0

        // === ЗОНА 1: ВИДЕОПОТОК (Слева) ===
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: "black"

            Image {
                id: camView
                anchors.fill: parent
                fillMode: Image.PreserveAspectFit
                source: cameraController.imagePath 
                cache: false
            }

            // Оверлей статуса
            Rectangle {
                anchors { left: parent.left; top: parent.top; margins: 20 }
                width: childrenRect.width + 30; height: 40
                radius: 8
                color: "#aa000000"
                border.color: cameraController.status === "ONLINE" ? "#00e676" : "#ff1744"
                
                Text {
                    anchors.centerIn: parent
                    text: "STATUS: " + cameraController.status
                    color: "white"
                    font.bold: true
                }
            }
        }

        // === ЗОНА 2: ПАНЕЛЬ УПРАВЛЕНИЯ (Справа) ===
        Rectangle {
            Layout.preferredWidth: 350
            Layout.fillHeight: true
            color: "#1e1e1e"
            
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 20
                spacing: 20

                Text {
                    text: "CONTROL MODULE"
                    color: "#808080"
                    font.pixelSize: 14
                    font.bold: true
                    Layout.alignment: Qt.AlignHCenter
                }
                
                // КНОПКИ УПРАВЛЕНИЯ
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 15

                    // === [MODIFIED] БОЛЬШАЯ КНОПКА СТАРТ ===
                    Button {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 120 // Сделали большой размер
                        
                        // Блокируем кнопку, если камера уже работает
                        enabled: cameraController.status !== "ONLINE"
                        
                        text: "ЗАПУСК"
                        font.pixelSize: 32
                        font.bold: true
                        
                        highlighted: true
                        Material.accent: Material.Green // Ярко-зеленый цвет
                        
                        onClicked: cameraController.start_camera()
                    }

                    // КНОПКА ЗАПИСИ
                    Button {
                        Layout.fillWidth: true; Layout.preferredHeight: 80
                        enabled: cameraController.status === "ONLINE"
                        onClicked: cameraController.toggle_recording()
                        
                        background: Rectangle { 
                            color: cameraController.isRecording ? "#ff1744" : "#2196f3"
                            radius: 12
                            opacity: parent.enabled ? 1 : 0.3 
                            
                            // Пульсация при записи
                            SequentialAnimation on opacity {
                                running: cameraController.isRecording
                                loops: Animation.Infinite
                                NumberAnimation { from: 1; to: 0.6; duration: 800 }
                                NumberAnimation { from: 0.6; to: 1; duration: 800 }
                            }
                        }
                        
                        contentItem: RowLayout {
                            anchors.centerIn: parent
                            spacing: 15
                            Rectangle {
                                width: 24; height: 24; radius: 12
                                color: "white"
                                visible: cameraController.isRecording
                            }
                            Text { 
                                text: cameraController.isRecording ? "ИДЕТ ЗАПИСЬ..." : "ЗАПИСЬ RAW"
                                font.pixelSize: 22; font.bold: true; color: "white" 
                            }
                        }
                    }
                    
                    // СТОП (Отдельно, красный)
                    Button {
                        Layout.fillWidth: true; Layout.preferredHeight: 60
                        text: "ОТКЛЮЧИТЬ ПИТАНИЕ"
                        
                        highlighted: true
                        Material.accent: Material.Red
                        
                        enabled: cameraController.status === "ONLINE"
                        onClicked: cameraController.stop_camera()
                    }
                }

                Item { Layout.fillHeight: true } // Распорка

                // GAIN CONTROL
                Rectangle {
                    Layout.fillWidth: true; Layout.preferredHeight: 120
                    color: "#2c2c2c"; radius: 12
                    
                    ColumnLayout {
                        anchors.fill: parent; anchors.margins: 15
                        Text { text: "Усиление (Gain)"; color: "white"; font.bold: true }
                        
                        Slider {
                            Layout.fillWidth: true
                            from: 0; to: 40; stepSize: 1
                            value: cameraController.gainValue
                            onMoved: cameraController.gainValue = value
                        }
                        
                        Text { 
                            text: (1.0 + cameraController.gainValue/20.0).toFixed(1) + "x"
                            color: "#00e676"; font.bold: true
                            Layout.alignment: Qt.AlignRight
                        }
                    }
                }

                // FPS COUNTER
                Rectangle {
                    Layout.fillWidth: true; Layout.preferredHeight: 100
                    color: "#252525"; radius: 12
                    border.color: "#333"
                    
                    RowLayout {
                        anchors.centerIn: parent
                        spacing: 20
                        Text { 
                            text: "FPS"; color: "#aaa"; font.pixelSize: 24; 
                            font.bold: true; verticalAlignment: Text.AlignBottom; bottomPadding: 6 
                        }
                        Text {
                            text: Math.round(cameraController.currentFps * 10) / 10
                            color: cameraController.currentFps > 24 ? "#00e676" : "#ff3d00"
                            font.pixelSize: 48; font.bold: true
                        }
                    }
                }
                
                Item { height: 10 }
            }
        }
    }
}