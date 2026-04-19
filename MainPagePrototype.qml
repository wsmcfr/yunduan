import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

/*
 * 主页面原型文件
 * 作用：
 * 1. 给 1024x600 RGB 屏提供一个可直接参考的主页面布局。
 * 2. 演示顶部状态栏、左侧导航、实时画面区、右侧结果区和底部统计栏的组织方式。
 * 3. 预留后续接入 C++ 控制器时需要绑定的关键属性。
 */
ApplicationWindow {
    id: root

    /*
     * 页面基础尺寸
     * 作用：与当前 7 寸 1024x600 屏幕保持一致，便于后续直接适配 eglfs 全屏显示。
     */
    width: 1024
    height: 600
    visible: true
    title: "工业缺陷检测系统 - 主页面原型"
    color: "#0b1520"

    /*
     * 运行状态相关属性
     * 作用：这些属性在真实项目中应由 C++ 后端控制器通过 Q_PROPERTY 暴露给 QML。
     */
    property string currentTimeText: "23:45:18"
    property bool networkOnline: true
    property bool cameraOnline: true
    property bool f4Online: true
    property bool armReady: true
    property bool cloudOnline: true
    property bool backlightAlwaysOn: true

    /*
     * 当前检测结果属性
     * 作用：用于右侧结果面板和底部统计条的实时显示。
     */
    property string partName: "平垫圈 A"
    property string currentStateText: "居中锁定"
    property int dxPixels: 3
    property string surfaceResultText: "正常"
    property string backlightResultText: "孔位正常"
    property string eddyResultText: "正常"
    property string finalResultText: "良品"
    property int confidenceScore: 962
    property int currentBeatMs: 830

    /*
     * 今日统计数据
     * 作用：模拟首页底部统计栏数据，后续应绑定数据库或统计模型。
     */
    property int dailyTotal: 1256
    property int dailyGood: 1218
    property int dailyBad: 38
    property string latestUploadText: "成功"

    /*
     * 最近记录列表
     * 作用：模拟底部最近记录滚动信息。
     */
    property var recentRecords: [
        "#1256 良品",
        "#1255 坏品",
        "#1254 良品"
    ]

    /*
     * 缺陷框数据
     * 作用：模拟叠加层显示的检测框，后续可由算法输出的坐标直接驱动。
     */
    property var defectBoxes: [
        { x: 120, y: 72, w: 88, h: 44, color: "#ff5a5f", label: "ROI" },
        { x: 270, y: 124, w: 64, h: 38, color: "#00d084", label: "目标" }
    ]

    /*
     * 状态颜色函数
     * 作用：根据文本结果返回对应颜色，便于界面快速区分正常、告警和离线状态。
     * 参数：
     * - text：状态文本
     * 返回值：
     * - 对应的颜色字符串
     */
    function statusColor(text) {
        if (text === "良品" || text === "正常" || text === "在线" || text === "待命") {
            return "#18c37e"
        }
        if (text === "坏品" || text === "异常" || text === "离线") {
            return "#ff5a5f"
        }
        if (text === "居中锁定" || text === "检测中") {
            return "#f6c344"
        }
        return "#8aa0b5"
    }

    /*
     * 统计文本格式化函数
     * 作用：将节拍毫秒数格式化为秒显示，便于比赛展示时直观看到单件耗时。
     * 参数：
     * - beatMs：毫秒值
     * 返回值：
     * - 格式化后的秒数字符串
     */
    function beatText(beatMs) {
        return (beatMs / 1000.0).toFixed(2) + "s"
    }

    Rectangle {
        anchors.fill: parent
        color: "#0b1520"

        /*
         * 顶部状态栏
         * 作用：显示系统时钟、关键设备在线状态和“背光常亮”固定状态。
         */
        Rectangle {
            id: topBar
            x: 0
            y: 0
            width: parent.width
            height: 56
            color: "#112234"

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 16
                anchors.rightMargin: 16
                spacing: 18

                Label {
                    text: "Defect Inspector"
                    color: "#f1f5f9"
                    font.pixelSize: 22
                    font.bold: true
                }

                Item { Layout.fillWidth: true }

                Label {
                    text: currentTimeText
                    color: "#dbe7f1"
                    font.pixelSize: 18
                }

                Repeater {
                    model: [
                        { name: "网络", text: networkOnline ? "在线" : "离线" },
                        { name: "相机", text: cameraOnline ? "在线" : "离线" },
                        { name: "F4", text: f4Online ? "在线" : "离线" },
                        { name: "机械臂", text: armReady ? "待命" : "忙碌" },
                        { name: "背光", text: backlightAlwaysOn ? "常亮" : "关闭" },
                        { name: "云端", text: cloudOnline ? "在线" : "离线" }
                    ]

                    delegate: RowLayout {
                        spacing: 6

                        Rectangle {
                            width: 10
                            height: 10
                            radius: 5
                            color: statusColor(modelData.text === "常亮" ? "在线" : modelData.text)
                        }

                        Label {
                            text: modelData.name + ":" + modelData.text
                            color: "#dbe7f1"
                            font.pixelSize: 15
                        }
                    }
                }
            }
        }

        /*
         * 左侧导航栏
         * 作用：提供页面切换入口。原型里只做视觉展示，不真正切换页面。
         */
        Rectangle {
            id: navPanel
            x: 0
            y: topBar.height
            width: 160
            height: parent.height - topBar.height
            color: "#0f1d2d"

            Column {
                anchors.fill: parent
                anchors.margins: 14
                spacing: 12

                Repeater {
                    model: ["首页", "历史记录", "统计分析", "手动控制", "参数设置", "告警维护"]

                    delegate: Rectangle {
                        width: 132
                        height: 52
                        radius: 12
                        color: index === 0 ? "#1e3a5f" : "#15273c"
                        border.width: 1
                        border.color: index === 0 ? "#2f6fb2" : "#203851"

                        Label {
                            anchors.centerIn: parent
                            text: modelData
                            color: "#e6eef7"
                            font.pixelSize: 18
                            font.bold: index === 0
                        }
                    }
                }
            }
        }

        /*
         * 主内容区容器
         * 作用：承载实时画面、右侧结果卡和底部统计条。
         */
        Item {
            id: contentArea
            x: navPanel.width
            y: topBar.height
            width: parent.width - navPanel.width
            height: parent.height - topBar.height

            /*
             * 实时画面区
             * 作用：后续可替换成 VideoOutput 或算法处理后的 QImage。
             */
            Rectangle {
                id: videoPanel
                x: 16
                y: 16
                width: 560
                height: 330
                radius: 16
                color: "#09121d"
                border.width: 2
                border.color: "#233a52"

                Label {
                    anchors.left: parent.left
                    anchors.top: parent.top
                    anchors.leftMargin: 14
                    anchors.topMargin: 10
                    text: "实时画面 / 中心定位 / 缺陷叠加"
                    color: "#c7d4e2"
                    font.pixelSize: 18
                    font.bold: true
                }

                /*
                 * 模拟画面背景
                 * 作用：用渐变色占位，实际项目应替换成相机帧。
                 */
                Rectangle {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    anchors.margins: 16
                    radius: 12
                    color: "#142437"

                    Canvas {
                        id: overlayCanvas
                        anchors.fill: parent

                        /*
                         * 叠加层绘制逻辑
                         * 作用：绘制中心十字线、ROI 框和模拟缺陷框。
                         */
                        onPaint: {
                            var ctx = getContext("2d")
                            ctx.clearRect(0, 0, width, height)

                            ctx.strokeStyle = "#5ea9ff"
                            ctx.lineWidth = 2

                            // 绘制中心十字线
                            ctx.beginPath()
                            ctx.moveTo(width / 2, 20)
                            ctx.lineTo(width / 2, height - 20)
                            ctx.moveTo(20, height / 2)
                            ctx.lineTo(width - 20, height / 2)
                            ctx.stroke()

                            // 绘制中心参考框
                            ctx.strokeStyle = "#f6c344"
                            ctx.strokeRect(width / 2 - 80, height / 2 - 55, 160, 110)

                            // 绘制模拟缺陷框和文字
                            for (var i = 0; i < defectBoxes.length; ++i) {
                                var box = defectBoxes[i]
                                ctx.strokeStyle = box.color
                                ctx.lineWidth = 2
                                ctx.strokeRect(box.x, box.y, box.w, box.h)
                                ctx.fillStyle = box.color
                                ctx.font = "14px Sans"
                                ctx.fillText(box.label, box.x + 4, box.y - 6)
                            }
                        }
                    }

                    Label {
                        anchors.centerIn: parent
                        text: "这里替换成 UVC 摄像头实时画面"
                        color: "#7f96ab"
                        font.pixelSize: 20
                    }
                }
            }

            /*
             * 右侧结果面板
             * 作用：集中显示当前零件状态、三路检测结果和操作按钮。
             */
            Rectangle {
                id: resultPanel
                x: 592
                y: 16
                width: 256
                height: 330
                radius: 16
                color: "#112031"
                border.width: 2
                border.color: "#223a53"

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 10

                    Label {
                        text: "当前检测结果"
                        color: "#f2f7fb"
                        font.pixelSize: 20
                        font.bold: true
                    }

                    Repeater {
                        model: [
                            { name: "当前零件", value: partName, color: "#dce6ef" },
                            { name: "当前状态", value: currentStateText, color: statusColor(currentStateText) },
                            { name: "视觉偏差", value: "dx=" + dxPixels + " px", color: "#dce6ef" },
                            { name: "表面结果", value: surfaceResultText, color: statusColor(surfaceResultText) },
                            { name: "背光结果", value: backlightResultText, color: "#dce6ef" },
                            { name: "涡流结果", value: eddyResultText, color: statusColor(eddyResultText) },
                            { name: "融合结果", value: finalResultText, color: statusColor(finalResultText) },
                            { name: "置信度", value: confidenceScore + "/1000", color: "#f6c344" },
                            { name: "背光状态", value: backlightAlwaysOn ? "常亮" : "关闭", color: "#18c37e" }
                        ]

                        delegate: Rectangle {
                            Layout.fillWidth: true
                            height: 28
                            radius: 8
                            color: "#16283c"

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 10
                                anchors.rightMargin: 10

                                Label {
                                    text: modelData.name
                                    color: "#aabccc"
                                    font.pixelSize: 14
                                }

                                Item { Layout.fillWidth: true }

                                Label {
                                    text: modelData.value
                                    color: modelData.color
                                    font.pixelSize: 14
                                    font.bold: true
                                }
                            }
                        }
                    }

                    Item { Layout.fillHeight: true }

                    GridLayout {
                        columns: 2
                        rowSpacing: 10
                        columnSpacing: 10
                        Layout.fillWidth: true

                        Repeater {
                            model: ["开始", "暂停", "单步", "复位"]

                            delegate: Button {
                                text: modelData
                                Layout.fillWidth: true
                                Layout.preferredHeight: 42
                            }
                        }
                    }
                }
            }

            /*
             * 底部统计区
             * 作用：显示统计信息和最近记录，适合比赛演示时让评委快速理解系统运行情况。
             */
            Rectangle {
                id: statsPanel
                x: 16
                y: 362
                width: 832
                height: 166
                radius: 16
                color: "#101d2c"
                border.width: 2
                border.color: "#223a53"

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 12

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 18

                        Repeater {
                            model: [
                                { name: "总检测数", value: dailyTotal },
                                { name: "良品数", value: dailyGood },
                                { name: "坏品数", value: dailyBad },
                                { name: "当前节拍", value: beatText(currentBeatMs) },
                                { name: "最近上传", value: latestUploadText }
                            ]

                            delegate: Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 48
                                radius: 10
                                color: "#17283b"

                                Column {
                                    anchors.centerIn: parent
                                    spacing: 2

                                    Label {
                                        text: modelData.name
                                        color: "#96a9bc"
                                        font.pixelSize: 13
                                        horizontalAlignment: Text.AlignHCenter
                                    }

                                    Label {
                                        text: modelData.value
                                        color: "#f2f7fb"
                                        font.pixelSize: 18
                                        font.bold: true
                                        horizontalAlignment: Text.AlignHCenter
                                    }
                                }
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        radius: 10
                        color: "#17283b"

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 12
                            anchors.rightMargin: 12
                            spacing: 16

                            Label {
                                text: "最近记录:"
                                color: "#aabccc"
                                font.pixelSize: 15
                            }

                            Repeater {
                                model: recentRecords

                                delegate: Rectangle {
                                    radius: 8
                                    color: index === 1 ? "#472329" : "#1e3448"
                                    height: 32
                                    width: 120

                                    Label {
                                        anchors.centerIn: parent
                                        text: modelData
                                        color: "#eef4f9"
                                        font.pixelSize: 14
                                    }
                                }
                            }

                            Item { Layout.fillWidth: true }
                        }
                    }
                }
            }
        }
    }
}
