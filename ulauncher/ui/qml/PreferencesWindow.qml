import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ApplicationWindow {
    id: root

    property var backend
    property string requestedPage: "general"
    readonly property var pageIds: ["general", "features", "web-search", "shortcuts", "extensions", "desktop", "about"]

    title: backend ? backend.appName + " Preferences" : "Preferences"
    visible: false
    width: 920
    height: 700
    minimumWidth: 720
    minimumHeight: 480

    pageStack.globalToolBar.style: Kirigami.ApplicationHeaderStyle.None

    onRequestedPageChanged: {
        const index = pageIds.indexOf(requestedPage)
        if (index >= 0)
            sideList.currentIndex = index
    }

    // ---------- reusable setting controls ----------

    component SettingSwitch: QQC2.Switch {
        property string settingKey
        Component.onCompleted: checked = root.backend.getSetting(settingKey) === true
        onToggled: root.backend.setSetting(settingKey, checked)
    }

    component SettingSpin: QQC2.SpinBox {
        property string settingKey
        Component.onCompleted: value = Number(root.backend.getSetting(settingKey))
        onValueModified: root.backend.setSetting(settingKey, value)
    }

    component SettingCombo: QQC2.ComboBox {
        property string settingKey
        property var entries: []  // [{text, value}]
        textRole: "text"
        model: entries
        Component.onCompleted: {
            const current = root.backend.getSetting(settingKey)
            for (let i = 0; i < entries.length; i++) {
                if (entries[i].value === current) {
                    currentIndex = i
                    break
                }
            }
        }
        onActivated: root.backend.setSetting(settingKey, entries[currentIndex].value)
    }

    component SettingText: QQC2.TextField {
        property string settingKey
        Component.onCompleted: text = String(root.backend.getSetting(settingKey) || "")
        onEditingFinished: root.backend.setSetting(settingKey, text)
    }

    pageStack.initialPage: Kirigami.Page {
        padding: 0

        RowLayout {
            anchors.fill: parent
            spacing: 0

            QQC2.ScrollView {
                id: scrollArea1
                Layout.fillHeight: true
                Layout.preferredWidth: 200

                ListView {
                    id: sideList
                    currentIndex: 0
                    model: ListModel {
                        ListElement { label: "General"; icon: "preferences-desktop-theme-global"; page: "general" }
                        ListElement { label: "Features"; icon: "search"; page: "features" }
                        ListElement { label: "Web Search"; icon: "globe"; page: "web-search" }
                        ListElement { label: "Shortcuts"; icon: "link"; page: "shortcuts" }
                        ListElement { label: "Extensions"; icon: "plugins"; page: "extensions" }
                        ListElement { label: "Desktop"; icon: "preferences-system-startup"; page: "desktop" }
                        ListElement { label: "About"; icon: "help-about"; page: "about" }
                    }
                    delegate: QQC2.ItemDelegate {
                        required property int index
                        required property var model
                        width: sideList.width
                        text: model.label
                        icon.name: model.icon
                        highlighted: sideList.currentIndex === index
                        onClicked: sideList.currentIndex = index
                    }
                }
            }

            Kirigami.Separator {
                Layout.fillHeight: true
            }

            StackLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                currentIndex: sideList.currentIndex

                // ---------- General ----------
                QQC2.ScrollView {
                    id: scrollArea2
                    contentWidth: availableWidth

                    ColumnLayout {
                        width: scrollArea2.availableWidth
                        spacing: Kirigami.Units.largeSpacing

                        Kirigami.FormLayout {
                            Layout.fillWidth: true
                            Layout.margins: Kirigami.Units.largeSpacing * 2

                            Kirigami.Separator {
                                Kirigami.FormData.label: "Appearance"
                                Kirigami.FormData.isSection: true
                            }

                            SettingCombo {
                                Kirigami.FormData.label: "Color scheme:"
                                settingKey: "color_scheme"
                                entries: [
                                    { text: "Follow system", value: "system" },
                                    { text: "Light", value: "light" },
                                    { text: "Dark", value: "dark" }
                                ]
                            }

                            SettingCombo {
                                Kirigami.FormData.label: "Position:"
                                settingKey: "popup_position"
                                entries: [
                                    { text: "Center", value: "center" },
                                    { text: "Top", value: "top" }
                                ]
                            }

                            SettingCombo {
                                Kirigami.FormData.label: "Row density:"
                                settingKey: "row_density"
                                entries: [
                                    { text: "Comfortable", value: "comfortable" },
                                    { text: "Compact", value: "compact" }
                                ]
                            }

                            SettingCombo {
                                Kirigami.FormData.label: "Result order:"
                                settingKey: "result_order"
                                entries: [
                                    { text: "Apps first", value: "default" },
                                    { text: "Windows first", value: "windows-first" }
                                ]
                            }

                            SettingSpin {
                                Kirigami.FormData.label: "Popup width:"
                                settingKey: "base_width"
                                from: 400; to: 1200; stepSize: 20
                            }

                            SettingSpin {
                                Kirigami.FormData.label: "Results max height:"
                                settingKey: "results_max_height"
                                from: 160; to: 800; stepSize: 20
                            }

                            SettingSpin {
                                Kirigami.FormData.label: "Max results per category:"
                                settingKey: "max_per_category"
                                from: 1; to: 20
                            }

                            SettingSpin {
                                Kirigami.FormData.label: "Result icon size:"
                                settingKey: "icon_size"
                                from: 16; to: 64; stepSize: 2
                            }

                            SettingSwitch {
                                Kirigami.FormData.label: "Show search icon:"
                                settingKey: "show_search_icon"
                            }

                            SettingSwitch {
                                Kirigami.FormData.label: "Show section headers:"
                                settingKey: "show_section_headers"
                            }

                            SettingSwitch {
                                Kirigami.FormData.label: "Show result icons:"
                                settingKey: "show_result_icons"
                            }

                            SettingSwitch {
                                Kirigami.FormData.label: "Show descriptions:"
                                settingKey: "show_descriptions"
                            }

                            SettingSwitch {
                                Kirigami.FormData.label: "Show numbers (activate with Alt+digit):"
                                settingKey: "show_result_numbers"
                            }

                            Kirigami.Separator {
                                Kirigami.FormData.label: "Global Shortcut"
                                Kirigami.FormData.isSection: true
                            }

                            QQC2.Button {
                                id: shortcutButton
                                Kirigami.FormData.label: "Toggle shortcut:"
                                property bool capturing: false
                                text: capturing ? "Press a key combination..."
                                                : (root.backend ? root.backend.currentShortcutLabel : "")
                                onClicked: {
                                    capturing = true
                                    forceActiveFocus()
                                }
                                Keys.onPressed: (event) => {
                                    if (!capturing)
                                        return
                                    if (event.key === Qt.Key_Escape) {
                                        capturing = false
                                        event.accepted = true
                                        return
                                    }
                                    const accel = root.backend.acceleratorFromKey(event.key, event.modifiers)
                                    if (accel.length > 0) {
                                        capturing = false
                                        if (!root.backend.applyAccelerator(accel))
                                            root.showPassiveNotification("Could not grab the shortcut")
                                    }
                                    event.accepted = true
                                }
                                onActiveFocusChanged: {
                                    if (!activeFocus)
                                        capturing = false
                                }
                            }

                            QQC2.Button {
                                Kirigami.FormData.label: "Reset to default:"
                                text: "Reset (Ctrl+Space)"
                                onClicked: root.backend.applyAccelerator("<Control>space")
                            }

                            QQC2.Button {
                                visible: root.backend && root.backend.isPlasma
                                Kirigami.FormData.label: "Plasma shortcuts:"
                                text: "Open keyboard settings"
                                onClicked: root.backend.openPlasmaShortcuts()
                            }
                        }
                    }
                }

                // ---------- Features ----------
                QQC2.ScrollView {
                    id: scrollArea3
                    contentWidth: availableWidth

                    Kirigami.FormLayout {
                        width: scrollArea3.availableWidth

                        Kirigami.Separator {
                            Kirigami.FormData.label: "Search Providers"
                            Kirigami.FormData.isSection: true
                        }

                        SettingSwitch { Kirigami.FormData.label: "Applications:"; settingKey: "enable_application_mode" }
                        SettingSwitch { Kirigami.FormData.label: "Application actions:"; settingKey: "enable_app_actions" }
                        SettingSwitch { Kirigami.FormData.label: "Calculator:"; settingKey: "enable_calculator" }
                        SettingSwitch { Kirigami.FormData.label: "Unit conversion:"; settingKey: "enable_unit_convert" }
                        SettingSwitch { Kirigami.FormData.label: "Color codes:"; settingKey: "enable_color_hex" }
                        SettingSwitch { Kirigami.FormData.label: "Window search:"; settingKey: "enable_window_search" }
                        SettingSwitch { Kirigami.FormData.label: "System actions:"; settingKey: "enable_system_actions" }
                        SettingSwitch { Kirigami.FormData.label: "Settings search:"; settingKey: "enable_settings_search" }
                        SettingSwitch { Kirigami.FormData.label: "Recent files:"; settingKey: "enable_recent_files" }
                        SettingSwitch { Kirigami.FormData.label: "Open URLs:"; settingKey: "enable_url_open" }
                        SettingSwitch { Kirigami.FormData.label: "Open paths:"; settingKey: "enable_path_open" }
                        SettingSwitch { Kirigami.FormData.label: "Places:"; settingKey: "enable_places" }
                        SettingSwitch { Kirigami.FormData.label: "Bookmarks:"; settingKey: "enable_bookmarks" }
                        SettingSwitch { Kirigami.FormData.label: "Time and date:"; settingKey: "enable_time_date" }
                        SettingSwitch { Kirigami.FormData.label: "Run commands (! prefix):"; settingKey: "enable_command_run" }

                        Kirigami.Separator {
                            Kirigami.FormData.label: "Behavior"
                            Kirigami.FormData.isSection: true
                        }

                        SettingSwitch { Kirigami.FormData.label: "Prefix modes (= @ # $ . !):"; settingKey: "enable_prefix_modes" }
                        SettingSwitch { Kirigami.FormData.label: "Suggestions when empty:"; settingKey: "enable_empty_suggestions" }
                    }
                }

                // ---------- Web Search ----------
                QQC2.ScrollView {
                    id: scrollArea4
                    contentWidth: availableWidth

                    Kirigami.FormLayout {
                        width: scrollArea4.availableWidth

                        SettingSwitch { Kirigami.FormData.label: "Show web search:"; settingKey: "show_web_search" }

                        SettingCombo {
                            Kirigami.FormData.label: "Search engine:"
                            settingKey: "web_search_engine"
                            Component.onCompleted: {
                                const engines = root.backend.webSearchEngines()
                                let list = []
                                for (let i = 0; i < engines.length; i++)
                                    list.push({ text: engines[i].title, value: engines[i].id })
                                entries = list
                                const current = root.backend.getSetting(settingKey)
                                for (let i = 0; i < list.length; i++) {
                                    if (list[i].value === current)
                                        currentIndex = i
                                }
                            }
                        }
                    }
                }

                // ---------- Shortcuts ----------
                RowLayout {
                    spacing: 0

                    ColumnLayout {
                        Layout.preferredWidth: 260
                        Layout.fillHeight: true
                        spacing: 0

                        QQC2.ScrollView {
                            id: scrollArea5
                            Layout.fillWidth: true
                            Layout.fillHeight: true

                            ListView {
                                id: shortcutList
                                property var items: root.backend ? root.backend.shortcuts() : []
                                model: items
                                delegate: QQC2.ItemDelegate {
                                    required property int index
                                    required property var modelData
                                    width: shortcutList.width
                                    text: modelData.name
                                    icon.name: "link"
                                    highlighted: shortcutList.currentIndex === index
                                    onClicked: {
                                        shortcutList.currentIndex = index
                                        shortcutEditor.load(modelData)
                                    }
                                }
                                Connections {
                                    target: root.backend
                                    function onShortcutsChanged() {
                                        shortcutList.items = root.backend.shortcuts()
                                    }
                                }
                            }
                        }

                        QQC2.Button {
                            Layout.fillWidth: true
                            Layout.margins: Kirigami.Units.smallSpacing
                            text: "Add Shortcut"
                            icon.name: "list-add"
                            onClicked: {
                                shortcutList.currentIndex = -1
                                shortcutEditor.loadNew()
                            }
                        }
                    }

                    Kirigami.Separator { Layout.fillHeight: true }

                    QQC2.ScrollView {
                        id: scrollArea6
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        contentWidth: availableWidth

                        ColumnLayout {
                            id: shortcutEditor
                            width: scrollArea6.availableWidth

                            property string editingId: ""
                            property bool active: false

                            function load(data) {
                                editingId = data.id
                                nameField.text = data.name
                                keywordField.text = data.keyword
                                cmdArea.text = data.cmd
                                staticSwitch.checked = data.run_without_argument
                                fallbackSwitch.checked = data.is_default_search
                                active = true
                            }

                            function loadNew() {
                                editingId = ""
                                nameField.text = ""
                                keywordField.text = ""
                                cmdArea.text = ""
                                staticSwitch.checked = false
                                fallbackSwitch.checked = false
                                active = true
                            }

                            QQC2.Label {
                                visible: !shortcutEditor.active
                                Layout.margins: Kirigami.Units.largeSpacing * 2
                                text: "Select a shortcut to edit, or create a new one"
                                opacity: 0.6
                            }

                            Kirigami.FormLayout {
                                visible: shortcutEditor.active
                                Layout.fillWidth: true
                                Layout.margins: Kirigami.Units.largeSpacing * 2

                                QQC2.TextField {
                                    id: nameField
                                    Kirigami.FormData.label: "Name:"
                                }

                                QQC2.TextField {
                                    id: keywordField
                                    Kirigami.FormData.label: "Keyword:"
                                }

                                QQC2.TextArea {
                                    id: cmdArea
                                    Kirigami.FormData.label: "Query or script:"
                                    Layout.fillWidth: true
                                    Layout.minimumHeight: 120
                                    font.family: "monospace"
                                    wrapMode: TextEdit.NoWrap
                                }

                                QQC2.Label {
                                    text: "Use %s for the query argument, e.g. https://google.com/search?q=%s\nScripts must start with a shebang (#!) line; $* holds the arguments."
                                    font.pointSize: 8
                                    opacity: 0.6
                                }

                                QQC2.Switch {
                                    id: staticSwitch
                                    Kirigami.FormData.label: "Static shortcut (runs without argument):"
                                }

                                QQC2.Switch {
                                    id: fallbackSwitch
                                    Kirigami.FormData.label: "Use as fallback result:"
                                }

                                RowLayout {
                                    QQC2.Button {
                                        text: "Save"
                                        icon.name: "document-save"
                                        enabled: nameField.text.length > 0 && keywordField.text.length > 0 && cmdArea.text.length > 0
                                        onClicked: {
                                            const saved = root.backend.saveShortcut({
                                                id: shortcutEditor.editingId,
                                                name: nameField.text,
                                                keyword: keywordField.text,
                                                cmd: cmdArea.text,
                                                run_without_argument: staticSwitch.checked,
                                                is_default_search: fallbackSwitch.checked
                                            })
                                            if (saved)
                                                root.showPassiveNotification("Shortcut saved")
                                        }
                                    }

                                    QQC2.Button {
                                        text: "Remove"
                                        icon.name: "edit-delete"
                                        visible: shortcutEditor.editingId.length > 0
                                        onClicked: {
                                            root.backend.removeShortcut(shortcutEditor.editingId)
                                            shortcutEditor.active = false
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // ---------- Extensions ----------
                RowLayout {
                    spacing: 0

                    ColumnLayout {
                        Layout.preferredWidth: 260
                        Layout.fillHeight: true
                        spacing: 0

                        QQC2.ScrollView {
                            id: scrollArea7
                            Layout.fillWidth: true
                            Layout.fillHeight: true

                            ListView {
                                id: extList
                                property var items: []
                                model: items
                                function refresh() {
                                    items = root.backend.extensions()
                                    if (currentIndex >= 0 && currentIndex < items.length)
                                        extDetail.load(items[currentIndex])
                                }
                                Component.onCompleted: refresh()
                                delegate: QQC2.ItemDelegate {
                                    required property int index
                                    required property var modelData
                                    width: extList.width
                                    highlighted: extList.currentIndex === index
                                    contentItem: RowLayout {
                                        spacing: Kirigami.Units.smallSpacing
                                        Image {
                                            source: "image://appicon/" + encodeURIComponent(modelData.icon)
                                            sourceSize.width: 24
                                            sourceSize.height: 24
                                        }
                                        QQC2.Label {
                                            Layout.fillWidth: true
                                            text: modelData.name
                                            elide: Text.ElideRight
                                        }
                                        QQC2.Label {
                                            visible: modelData.status !== "on"
                                            text: modelData.status
                                            font.pointSize: 8
                                            opacity: 0.7
                                        }
                                    }
                                    onClicked: {
                                        extList.currentIndex = index
                                        extDetail.load(modelData)
                                    }
                                }
                                Connections {
                                    target: root.backend
                                    function onExtensionsChanged() {
                                        extList.refresh()
                                    }
                                    function onExtOpFinished(success, message) {
                                        root.showPassiveNotification(message)
                                    }
                                    function onUpdateCheckFinished(extId, updated, message) {
                                        root.showPassiveNotification(message)
                                    }
                                }
                            }
                        }

                        QQC2.Button {
                            Layout.fillWidth: true
                            Layout.margins: Kirigami.Units.smallSpacing
                            text: "Add extension"
                            icon.name: "list-add"
                            onClicked: addExtDialog.open()
                        }

                        QQC2.Button {
                            Layout.fillWidth: true
                            Layout.leftMargin: Kirigami.Units.smallSpacing
                            Layout.rightMargin: Kirigami.Units.smallSpacing
                            Layout.bottomMargin: Kirigami.Units.smallSpacing
                            text: "Discover extensions"
                            icon.name: "globe"
                            onClicked: root.backend.openUrl("https://ext.ulauncher.io/?versions=2%2C3")
                        }
                    }

                    Kirigami.Separator { Layout.fillHeight: true }

                    QQC2.ScrollView {
                        id: scrollArea8
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        contentWidth: availableWidth

                        ColumnLayout {
                            id: extDetail
                            width: scrollArea8.availableWidth

                            property var ext: null
                            property var pendingTriggers: ({})
                            property var pendingPrefs: ({})

                            function load(data) {
                                ext = data
                                pendingTriggers = {}
                                pendingPrefs = {}
                            }

                            QQC2.Label {
                                visible: !extDetail.ext
                                Layout.margins: Kirigami.Units.largeSpacing * 2
                                text: "Select an extension"
                                opacity: 0.6
                            }

                            ColumnLayout {
                                visible: !!extDetail.ext
                                Layout.fillWidth: true
                                Layout.margins: Kirigami.Units.largeSpacing * 2
                                spacing: Kirigami.Units.largeSpacing

                                RowLayout {
                                    spacing: Kirigami.Units.largeSpacing

                                    Image {
                                        source: extDetail.ext ? "image://appicon/" + encodeURIComponent(extDetail.ext.icon) : ""
                                        sourceSize.width: 48
                                        sourceSize.height: 48
                                    }

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 0

                                        Kirigami.Heading {
                                            level: 2
                                            text: extDetail.ext ? extDetail.ext.name : ""
                                        }

                                        QQC2.Label {
                                            text: extDetail.ext && extDetail.ext.authors.length > 0 ? "by " + extDetail.ext.authors : ""
                                            opacity: 0.7
                                            font.pointSize: 9
                                        }

                                        QQC2.Label {
                                            visible: extDetail.ext && extDetail.ext.updated.length > 0
                                            text: extDetail.ext ? "updated " + extDetail.ext.updated : ""
                                            opacity: 0.7
                                            font.pointSize: 9
                                        }
                                    }

                                    QQC2.Switch {
                                        checked: extDetail.ext ? extDetail.ext.enabled : false
                                        onToggled: root.backend.toggleExtension(extDetail.ext.id, checked)
                                    }
                                }

                                Kirigami.InlineMessage {
                                    Layout.fillWidth: true
                                    visible: extDetail.ext && extDetail.ext.error.length > 0
                                    type: Kirigami.MessageType.Error
                                    text: extDetail.ext ? extDetail.ext.error : ""
                                }

                                QQC2.Label {
                                    visible: extDetail.ext && extDetail.ext.instructions.length > 0
                                    Layout.fillWidth: true
                                    text: extDetail.ext ? extDetail.ext.instructions : ""
                                    wrapMode: Text.WordWrap
                                    textFormat: Text.StyledText
                                    font.pointSize: 9
                                    opacity: 0.8
                                }

                                Kirigami.FormLayout {
                                    Layout.fillWidth: true

                                    Repeater {
                                        model: extDetail.ext ? extDetail.ext.triggers : []

                                        QQC2.TextField {
                                            required property var modelData
                                            Kirigami.FormData.label: modelData.name + " keyword:"
                                            text: modelData.keyword
                                            onEditingFinished: {
                                                let pending = extDetail.pendingTriggers
                                                pending[modelData.id] = { keyword: text }
                                                extDetail.pendingTriggers = pending
                                            }
                                        }
                                    }

                                }

                                // Extension preferences (typed controls)
                                Repeater {
                                    model: extDetail.ext ? extDetail.ext.prefs : []

                                    ColumnLayout {
                                        required property var modelData
                                        Layout.fillWidth: true
                                        spacing: Kirigami.Units.smallSpacing

                                        QQC2.Label {
                                            text: modelData.name
                                            font.weight: Font.DemiBold
                                        }

                                        QQC2.Label {
                                            visible: modelData.description.length > 0
                                            Layout.fillWidth: true
                                            text: modelData.description
                                            wrapMode: Text.WordWrap
                                            font.pointSize: 9
                                            opacity: 0.7
                                        }

                                        QQC2.CheckBox {
                                            visible: modelData.type === "checkbox"
                                            checked: modelData.value === true || modelData.value === "true"
                                            onToggled: {
                                                let pending = extDetail.pendingPrefs
                                                pending[modelData.id] = checked
                                                extDetail.pendingPrefs = pending
                                            }
                                        }

                                        QQC2.SpinBox {
                                            visible: modelData.type === "number"
                                            from: Number(modelData.min)
                                            to: Number(modelData.max)
                                            value: Number(modelData.value) || 0
                                            onValueModified: {
                                                let pending = extDetail.pendingPrefs
                                                pending[modelData.id] = value
                                                extDetail.pendingPrefs = pending
                                            }
                                        }

                                        QQC2.ComboBox {
                                            visible: modelData.type === "select"
                                            textRole: "text"
                                            model: modelData.options
                                            Component.onCompleted: {
                                                for (let i = 0; i < modelData.options.length; i++) {
                                                    if (modelData.options[i].value === String(modelData.value))
                                                        currentIndex = i
                                                }
                                            }
                                            onActivated: {
                                                let pending = extDetail.pendingPrefs
                                                pending[modelData.id] = modelData.options[currentIndex].value
                                                extDetail.pendingPrefs = pending
                                            }
                                        }

                                        QQC2.TextArea {
                                            visible: modelData.type === "text"
                                            Layout.fillWidth: true
                                            Layout.minimumHeight: 80
                                            text: modelData.type === "text" ? String(modelData.value || "") : ""
                                            wrapMode: TextEdit.WordWrap
                                            onEditingFinished: {
                                                let pending = extDetail.pendingPrefs
                                                pending[modelData.id] = text
                                                extDetail.pendingPrefs = pending
                                            }
                                        }

                                        QQC2.TextField {
                                            visible: modelData.type !== "checkbox" && modelData.type !== "number"
                                                     && modelData.type !== "select" && modelData.type !== "text"
                                            Layout.fillWidth: true
                                            text: String(modelData.value || "")
                                            onEditingFinished: {
                                                let pending = extDetail.pendingPrefs
                                                pending[modelData.id] = text
                                                extDetail.pendingPrefs = pending
                                            }
                                        }
                                    }
                                }

                                RowLayout {
                                    spacing: Kirigami.Units.smallSpacing

                                    QQC2.Button {
                                        text: "Save"
                                        icon.name: "document-save"
                                        onClicked: {
                                            root.backend.saveExtensionPrefs(extDetail.ext.id, {
                                                triggers: extDetail.pendingTriggers,
                                                preferences: extDetail.pendingPrefs
                                            })
                                            root.showPassiveNotification("Extension preferences saved")
                                        }
                                    }

                                    QQC2.Button {
                                        visible: extDetail.ext && extDetail.ext.manageable && extDetail.ext.has_update_url
                                        text: "Check updates"
                                        icon.name: "view-refresh"
                                        onClicked: root.backend.updateExtension(extDetail.ext.id)
                                    }

                                    QQC2.Button {
                                        visible: extDetail.ext && extDetail.ext.manageable
                                        text: "Remove"
                                        icon.name: "edit-delete"
                                        onClicked: {
                                            root.backend.removeExtension(extDetail.ext.id)
                                            extDetail.ext = null
                                        }
                                    }

                                    QQC2.Button {
                                        visible: extDetail.ext && extDetail.ext.url.length > 0
                                        text: "Repository"
                                        icon.name: "globe"
                                        onClicked: root.backend.openUrl(extDetail.ext.url)
                                    }
                                }
                            }
                        }
                    }
                }

                // ---------- Desktop ----------
                QQC2.ScrollView {
                    id: scrollArea9
                    contentWidth: availableWidth

                    Kirigami.FormLayout {
                        width: scrollArea9.availableWidth

                        Kirigami.Separator {
                            Kirigami.FormData.label: "Session"
                            Kirigami.FormData.isSection: true
                        }

                        QQC2.Switch {
                            id: autostartSwitch
                            Kirigami.FormData.label: "Run in background:"
                            Component.onCompleted: checked = root.backend.autostartEnabled()
                            onToggled: {
                                if (!root.backend.setAutostart(checked))
                                    checked = !checked
                            }
                        }

                        SettingSwitch {
                            Kirigami.FormData.label: "Show tray icon:"
                            settingKey: "show_tray_icon"
                        }

                        SettingSwitch {
                            Kirigami.FormData.label: "Close when losing focus:"
                            settingKey: "close_on_focus_out"
                        }

                        SettingCombo {
                            Kirigami.FormData.label: "Screen to show on:"
                            settingKey: "render_on_screen"
                            entries: [
                                { text: "Default monitor", value: "default-monitor" },
                                { text: "Monitor with mouse pointer", value: "mouse-pointer-monitor" }
                            ]
                        }

                        Kirigami.Separator {
                            Kirigami.FormData.label: "Host"
                            Kirigami.FormData.isSection: true
                        }

                        SettingSwitch {
                            visible: root.backend && root.backend.isX11
                            Kirigami.FormData.label: "Switch to app if already running:"
                            settingKey: "raise_if_started"
                        }

                        SettingSwitch {
                            Kirigami.FormData.label: "Include foreign desktop apps:"
                            settingKey: "disable_desktop_filters"
                        }

                        SettingText {
                            Kirigami.FormData.label: "Terminal command:"
                            settingKey: "terminal_command"
                        }
                    }
                }

                // ---------- About ----------
                QQC2.ScrollView {
                    id: scrollArea10
                    contentWidth: availableWidth

                    ColumnLayout {
                        width: scrollArea10.availableWidth
                        spacing: Kirigami.Units.largeSpacing

                        Item { Layout.preferredHeight: Kirigami.Units.largeSpacing }

                        Kirigami.Icon {
                            Layout.alignment: Qt.AlignHCenter
                            source: "system-search"
                            Layout.preferredWidth: 64
                            Layout.preferredHeight: 64
                        }

                        Kirigami.Heading {
                            Layout.alignment: Qt.AlignHCenter
                            text: root.backend ? root.backend.appName : ""
                        }

                        QQC2.Label {
                            Layout.alignment: Qt.AlignHCenter
                            text: root.backend ? "Version " + root.backend.appVersion : ""
                            opacity: 0.7
                        }

                        QQC2.Label {
                            Layout.alignment: Qt.AlignHCenter
                            text: "Qt 6 + Kirigami launcher · GNU GPL v3.0"
                            opacity: 0.7
                            font.pointSize: 9
                        }

                        ColumnLayout {
                            Layout.alignment: Qt.AlignHCenter
                            spacing: Kirigami.Units.smallSpacing

                            Kirigami.UrlButton {
                                Layout.alignment: Qt.AlignHCenter
                                url: "https://github.com/goshitsarch-eng/GoshLauncher"
                                text: "GoshLauncher on GitHub"
                            }

                            Kirigami.UrlButton {
                                Layout.alignment: Qt.AlignHCenter
                                url: "https://github.com/Ulauncher/Ulauncher"
                                text: "Based on Ulauncher"
                            }
                        }
                    }
                }
            }
        }
    }

    Kirigami.PromptDialog {
        id: addExtDialog
        title: "Add Extension"
        standardButtons: Kirigami.Dialog.Ok | Kirigami.Dialog.Cancel

        QQC2.TextField {
            id: extUrlField
            placeholderText: "https://github.com/user/repo.git"
            Layout.fillWidth: true
        }

        onAccepted: {
            if (extUrlField.text.trim().length > 0) {
                root.backend.addExtension(extUrlField.text.trim())
                root.showPassiveNotification("Installing extension...")
            }
            extUrlField.text = ""
        }
    }
}
