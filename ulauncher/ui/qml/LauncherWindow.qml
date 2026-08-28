import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import QtQuick.Effects
import org.kde.kirigami as Kirigami

Window {
    id: root

    property var backend
    readonly property int shadowMargin: 24
    readonly property bool hasQuery: searchField.text.length > 0

    flags: Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint
    color: "transparent"
    visible: false
    title: "GoshLauncher"

    width: (backend ? backend.windowWidth : 600) + 2 * shadowMargin
    height: card.implicitHeight + 2 * shadowMargin

    onActiveChanged: {
        if (!active && visible && backend && backend.closeOnFocusOut)
            backend.requestClose()
    }

    onVisibleChanged: {
        if (visible)
            searchField.forceActiveFocus()
    }

    Connections {
        target: root.backend

        function onQueryTextRequested(text) {
            searchField.programmatic = true
            searchField.text = text
            searchField.cursorPosition = text.length
            searchField.programmatic = false
        }

        function onSelectedIndexChanged() {
            if (root.backend.selectedIndex >= 0)
                resultsList.positionViewAtIndex(root.backend.selectedIndex, ListView.Contain)
        }
    }

    MultiEffect {
        source: card
        anchors.fill: card
        z: -1
        shadowEnabled: true
        shadowColor: Qt.rgba(0, 0, 0, 0.55)
        shadowBlur: 1.0
        shadowVerticalOffset: 5
    }

    Rectangle {
        id: card

        anchors.fill: parent
        anchors.margins: root.shadowMargin
        implicitHeight: contentColumn.implicitHeight

        Kirigami.Theme.inherit: false
        Kirigami.Theme.colorSet: Kirigami.Theme.Window

        radius: Kirigami.Units.cornerRadius !== undefined ? Kirigami.Units.cornerRadius * 2 : 10
        color: Kirigami.Theme.backgroundColor
        border.width: 1
        border.color: Qt.alpha(Kirigami.Theme.textColor, 0.18)

        ColumnLayout {
            id: contentColumn
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            spacing: 0

            RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: Kirigami.Units.largeSpacing * 2
                Layout.rightMargin: Kirigami.Units.largeSpacing * 2
                Layout.topMargin: root.backend && root.backend.compactDensity ? Kirigami.Units.smallSpacing : Kirigami.Units.largeSpacing
                Layout.bottomMargin: root.backend && root.backend.compactDensity ? Kirigami.Units.smallSpacing : Kirigami.Units.largeSpacing
                spacing: Kirigami.Units.largeSpacing

                Kirigami.Icon {
                    visible: root.backend ? root.backend.showSearchIcon : true
                    source: "search"
                    Layout.preferredWidth: Kirigami.Units.iconSizes.smallMedium
                    Layout.preferredHeight: Kirigami.Units.iconSizes.smallMedium
                    opacity: 0.6
                }

                QQC2.TextField {
                    id: searchField

                    property bool programmatic: false

                    Layout.fillWidth: true
                    background: null
                    font.pointSize: root.backend && root.backend.compactDensity ? 12 : 15
                    placeholderText: root.backend ? root.backend.placeholderText : "Search..."
                    color: Kirigami.Theme.textColor
                    placeholderTextColor: Qt.alpha(Kirigami.Theme.textColor, 0.5)

                    onTextEdited: {
                        if (!programmatic && root.backend)
                            root.backend.textEdited(text)
                    }

                    Keys.onPressed: (event) => {
                        if (!root.backend)
                            return
                        const alt = event.modifiers & Qt.AltModifier
                        const ctrl = event.modifiers & Qt.ControlModifier
                        const shift = event.modifiers & Qt.ShiftModifier

                        if (event.key === Qt.Key_Escape) {
                            root.backend.requestClose()
                            event.accepted = true
                        } else if (ctrl && event.key === Qt.Key_Comma) {
                            root.backend.showPreferences()
                            event.accepted = true
                        } else if (event.key === Qt.Key_Backspace && !ctrl
                                   && searchField.selectedText.length === 0
                                   && searchField.cursorPosition === searchField.text.length) {
                            if (root.backend.handleBackspace(searchField.text))
                                event.accepted = true
                        } else if (ctrl && (event.key === Qt.Key_J || event.key === Qt.Key_N)) {
                            root.backend.navigate(1)
                            event.accepted = true
                        } else if (ctrl && (event.key === Qt.Key_K || event.key === Qt.Key_P)) {
                            root.backend.navigate(-1)
                            event.accepted = true
                        } else if (event.key === Qt.Key_Down) {
                            root.backend.navigate(1)
                            event.accepted = true
                        } else if (event.key === Qt.Key_Up) {
                            root.backend.navigate(-1)
                            event.accepted = true
                        } else if (event.key === Qt.Key_Tab || event.key === Qt.Key_Backtab) {
                            root.backend.navigate(event.key === Qt.Key_Backtab || shift ? -1 : 1)
                            event.accepted = true
                        } else if (event.key === Qt.Key_PageDown) {
                            root.backend.navigate(5)
                            event.accepted = true
                        } else if (event.key === Qt.Key_PageUp) {
                            root.backend.navigate(-5)
                            event.accepted = true
                        } else if (event.key === Qt.Key_Home && searchField.cursorPosition === 0) {
                            root.backend.navigate(-9999)
                            event.accepted = true
                        } else if (event.key === Qt.Key_End
                                   && searchField.cursorPosition === searchField.text.length) {
                            root.backend.navigate(9999)
                            event.accepted = true
                        } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                            root.backend.activateSelected(Boolean(alt))
                            event.accepted = true
                        } else if (alt && event.key >= Qt.Key_1 && event.key <= Qt.Key_9) {
                            root.backend.activateNumber(event.key - Qt.Key_0)
                            event.accepted = true
                        }
                    }
                }
            }

            Kirigami.Separator {
                Layout.fillWidth: true
                visible: resultsList.count > 0 || root.hasQuery
            }

            ListView {
                id: resultsList

                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(contentHeight, root.backend ? root.backend.resultsMaxHeight : 400)
                Layout.margins: resultsList.count > 0 ? Kirigami.Units.smallSpacing : 0
                visible: count > 0
                clip: true
                model: root.backend ? root.backend.model : null
                currentIndex: root.backend ? root.backend.selectedIndex : -1
                boundsBehavior: Flickable.StopAtBounds
                keyNavigationEnabled: false

                QQC2.ScrollBar.vertical: QQC2.ScrollBar {}

                delegate: Item {
                    id: row

                    required property int index
                    required property string name
                    required property string richName
                    required property string description
                    required property string icon
                    required property bool compact
                    required property bool isHeader
                    required property bool selectable
                    required property string numberHint
                    required property bool wrap

                    readonly property bool selected: root.backend && root.backend.selectedIndex === index

                    width: resultsList.width
                    height: rowContent.implicitHeight
                            + (isHeader ? Kirigami.Units.smallSpacing
                                        : (root.backend && root.backend.compactDensity
                                           ? Kirigami.Units.smallSpacing * 2 : Kirigami.Units.largeSpacing * 1.5))

                    Rectangle {
                        anchors.fill: parent
                        anchors.leftMargin: Kirigami.Units.smallSpacing
                        anchors.rightMargin: Kirigami.Units.smallSpacing
                        radius: 8
                        color: row.selected ? Kirigami.Theme.highlightColor : "transparent"
                    }

                    RowLayout {
                        id: rowContent
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.leftMargin: Kirigami.Units.largeSpacing * 2
                        anchors.rightMargin: Kirigami.Units.largeSpacing * 2
                        spacing: Kirigami.Units.largeSpacing

                        Image {
                            visible: !row.isHeader && (root.backend ? root.backend.showResultIcons : true) && row.icon.length > 0
                            source: row.icon.length > 0 ? "image://appicon/" + encodeURIComponent(row.icon) : ""
                            sourceSize.width: root.backend ? root.backend.iconSize : 28
                            sourceSize.height: root.backend ? root.backend.iconSize : 28
                            Layout.preferredWidth: root.backend ? root.backend.iconSize : 28
                            Layout.preferredHeight: root.backend ? root.backend.iconSize : 28
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0

                            QQC2.Label {
                                Layout.fillWidth: true
                                text: row.isHeader ? row.name.toUpperCase() : row.richName
                                textFormat: row.isHeader ? Text.PlainText : Text.StyledText
                                elide: row.wrap ? Text.ElideNone : Text.ElideRight
                                wrapMode: row.wrap ? Text.WordWrap : Text.NoWrap
                                maximumLineCount: row.wrap ? 8 : 1
                                font.pointSize: row.isHeader ? 8 : (root.backend && root.backend.compactDensity ? 10 : 11)
                                font.weight: row.isHeader ? Font.DemiBold : Font.Medium
                                font.letterSpacing: row.isHeader ? 1 : 0
                                opacity: row.isHeader ? 0.55 : 1
                                color: row.selected ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor
                            }

                            QQC2.Label {
                                Layout.fillWidth: true
                                visible: !row.compact && row.description.length > 0
                                         && (root.backend ? root.backend.showDescriptions : true)
                                text: row.description
                                elide: row.wrap ? Text.ElideNone : Text.ElideRight
                                wrapMode: row.wrap ? Text.WordWrap : Text.NoWrap
                                maximumLineCount: row.wrap ? 8 : 1
                                font.pointSize: 9
                                opacity: 0.7
                                color: row.selected ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor
                            }
                        }

                        QQC2.Label {
                            visible: root.backend && root.backend.showNumbers && row.numberHint.length > 0
                            text: row.numberHint
                            font.pointSize: 9
                            font.weight: Font.DemiBold
                            opacity: 0.6
                            color: row.selected ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        enabled: row.selectable
                        hoverEnabled: true
                        acceptedButtons: Qt.LeftButton | Qt.MiddleButton | Qt.RightButton
                        onEntered: root.backend.setHoverSelection(row.index)
                        onClicked: (mouse) => root.backend.activateIndex(row.index, mouse.button !== Qt.LeftButton)
                    }
                }
            }

            ColumnLayout {
                visible: resultsList.count === 0 && root.hasQuery
                Layout.fillWidth: true
                Layout.margins: Kirigami.Units.largeSpacing * 3
                spacing: Kirigami.Units.smallSpacing

                QQC2.Label {
                    Layout.alignment: Qt.AlignHCenter
                    text: "No Results"
                    font.weight: Font.DemiBold
                }

                QQC2.Label {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.maximumWidth: card.width - Kirigami.Units.largeSpacing * 6
                    text: 'No results for "' + searchField.text + '"'
                    elide: Text.ElideRight
                    opacity: 0.6
                    font.pointSize: 9
                }
            }
        }
    }
}
