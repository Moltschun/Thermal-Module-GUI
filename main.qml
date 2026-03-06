/*
 * Main Interface v4.2 (MATLAB Export Edition)
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

                    Button {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 120 
                        
                        enabled: cameraController.status !== "ONLINE"
                        
                        text: "ЗАПУСК"
                        font.pixelSize: 32
                        font.bold: true
                        
                        highlighted: true
                        Material.accent: Material.Green 
                        
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
                    
                    // СТОП
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

                Button {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 60
                    text: "СБОРКА .MAT"
                    font.bold: true
                    
                    enabled: !cameraController.isRecording
                    highlighted: true
                    Material.accent: Material.Orange 

                    // ИЗМЕНЕНО: Вызов нового метода контроллера
                    onClicked: cameraController.convert_to_mat()
                    
                    ToolTip.visible: hovered
                    ToolTip.text: "Собрать последнюю TIFF-сессию в массив Matlab"
                }

                Button {
                    id: calibButton
                    Layout.fillWidth: true
                    Layout.preferredHeight: 50
                    text: "CALIBRATE SENSOR"
                    enabled: cameraController.status !== "OFFLINE" // Активна только при включенной камере
                    
                    contentItem: RowLayout {
                        spacing: 10
                        anchors.centerIn: parent

                        Text {
                            text: "🔄" 
                            font.pixelSize: 18
                            color: calibButton.enabled ? "#00e676" : "#444"
                        }

                        Text {
                            text: "FFC CALIBRATION"
                            color: calibButton.enabled ? "white" : "#444"
                            font.bold: true
                            font.pixelSize: 14
                        }
                    }
                
                    background: Rectangle {
                        color: calibButton.pressed ? "#1b5e20" : (calibButton.enabled ? "#2e7d32" : "#1a1a1a")
                        radius: 8
                        border.color: calibButton.enabled ? "#00e676" : "#333"
                        border.width: 1
                    }
                
                    onClicked: {
                        cameraController.manualCalibration()
                    }
                }

                // Вставить в ColumnLayout правой панели управления

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 70
                    color: "#2c2c2c"
                    radius: 12
                
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 15
                        anchors.rightMargin: 15
                
                        ColumnLayout {
                            spacing: 2
                            Text { 
                                text: "РЕЖИМ ЗАПИСИ"
                                color: "#808080"
                                font.pixelSize: 10
                                font.bold: true
                            }
                            Text { 
                                text: cameraController.recordingMode === 0 ? "STATIC (25 FPS)" : "DYNAMIC (VFR)"
                                color: cameraController.recordingMode === 0 ? "#2196f3" : "#ff9800"
                                font.pixelSize: 14
                                font.bold: true
                            }
                        }
                
                        Item { Layout.fillWidth: true }
                
                        Switch {
                            checked: cameraController.recordingMode === 1
                            onToggled: {
                                cameraController.recordingMode = checked ? 1 : 0
                            }
                            
                            ToolTip.visible: hovered
                            ToolTip.text: "Вкл - Динамический (экономия), Выкл - Статический (25 FPS)"
                        }
                    }
                }

                
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