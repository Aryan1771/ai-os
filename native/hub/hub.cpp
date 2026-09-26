#include "hub.h"

#include <QApplication>
#include <QCheckBox>
#include <QCloseEvent>
#include <QColorDialog>
#include <QComboBox>
#include <QDesktopServices>
#include <QDir>
#include <QDateTime>
#include <QDoubleSpinBox>
#include <QFile>
#include <QFileDialog>
#include <QFileInfo>
#include <QFormLayout>
#include <QHBoxLayout>
#include <QJsonDocument>
#include <QLabel>
#include <QLineEdit>
#include <QListWidget>
#include <QMessageBox>
#include <QPlainTextEdit>
#include <QProcess>
#include <QProcessEnvironment>
#include <QProgressBar>
#include <QPushButton>
#include <QSaveFile>
#include <QScrollArea>
#include <QSlider>
#include <QSignalBlocker>
#include <QSplitter>
#include <QStackedWidget>
#include <QStyle>
#include <QTimer>
#include <QToolButton>
#include <QUrl>
#include <QVBoxLayout>
#include <memory>

namespace {
QJsonValue fieldValue(const QJsonObject &object, const QString &key) {
    const auto parts = key.split('.');
    return parts.size() == 2 ? object[parts[0]].toObject()[parts[1]] : object[key];
}
QPushButton *button(QWidget *parent, const QString &text, QStyle::StandardPixmap icon,
                    const std::function<void()> &action) {
    auto *result = new QPushButton(parent->style()->standardIcon(icon), text, parent);
    QObject::connect(result, &QPushButton::clicked, parent, action);
    return result;
}
QString replyText(const QJsonObject &response) {
    if (response["type"].toString() == "text") return response["content"].toString();
    return QString::fromUtf8(QJsonDocument(response).toJson(QJsonDocument::Indented));
}
}

Hub::Hub(QString interpreter, QString runtimeHome, bool connectBackend)
    : python(std::move(interpreter)), home(std::move(runtimeHome)) {
    setWindowTitle("REgenOS Hub");
    setMinimumSize(760, 560);
    resize(1100, 780);
    auto *central = new QWidget(this);
    setCentralWidget(central);
    auto *root = new QVBoxLayout(central);
    root->setContentsMargins(22, 18, 22, 18);
    auto *header = new QHBoxLayout;
    brand = new QLabel("REgenOS", this);
    brand->setObjectName("brand");
    header->addWidget(brand);
    header->addStretch();
    activity = new QLabel("Idle", this);
    activity->setObjectName("activity");
    header->addWidget(activity);
    root->addLayout(header);
    auto *body = new QHBoxLayout;
    body->setSpacing(24);
    navigation = new QListWidget(this);
    navigation->setObjectName("navigation");
    navigation->setFixedWidth(186);
    pages = new QStackedWidget(this);
    body->addWidget(navigation);
    body->addWidget(pages, 1);
    root->addLayout(body, 1);
    auto *footer = new QHBoxLayout;
    status = new QLabel("Connecting to local services...", this);
    status->setWordWrap(true);
    status->setObjectName("status");
    footer->addWidget(status, 1);
    reloadButton = button(this, "Reload", QStyle::SP_BrowserReload, [this] {
        if (collected() == saved || confirm("Unsaved settings", "Discard unsaved setting changes?")) reload();
    });
    saveButton = button(this, "Save changes", QStyle::SP_DialogSaveButton, [this] { save(); });
    saveButton->setObjectName("primary");
    footer->addWidget(reloadButton);
    footer->addWidget(saveButton);
    root->addLayout(footer);
    connect(navigation, &QListWidget::currentRowChanged, pages, &QStackedWidget::setCurrentIndex);
    applyTheme("graphite");
    auto *timer = new QTimer(this);
    connect(timer, &QTimer::timeout, this, &Hub::refreshActivity);
    timer->start(500);
    if (connectBackend) QTimer::singleShot(0, this, &Hub::reload);
}

Hub::~Hub() {
    // QProcess destruction can emit finished after child widgets have been deleted.
    for (auto *process : findChildren<QProcess *>()) {
        process->disconnect(this);
        if (process->state() != QProcess::NotRunning) {
            process->kill();
            process->waitForFinished(3000);
        }
    }
}

void Hub::applyTheme(const QString &name) {
    const bool light = name == "light";
    QString bg = light ? "#f3f3f3" : "#202020";
    QString surface = light ? "#ffffff" : "#2b2b2b";
    QString text = light ? "#202020" : "#e5e5e5";
    QString border = light ? "#d5d5d5" : "#404040";
    QString accent = "#79b8ec";
    if (name == "forest") accent = "#82c9aa";
    if (name == "ocean") accent = "#83c4d4";
    if (name == "sunrise") accent = "#e6b685";
    QPalette palette;
    palette.setColor(QPalette::Window, QColor(bg));
    palette.setColor(QPalette::WindowText, QColor(text));
    palette.setColor(QPalette::Base, QColor(surface));
    palette.setColor(QPalette::AlternateBase, QColor(bg));
    palette.setColor(QPalette::Text, QColor(text));
    palette.setColor(QPalette::Button, QColor(surface));
    palette.setColor(QPalette::ButtonText, QColor(text));
    palette.setColor(QPalette::Highlight, QColor(accent));
    palette.setColor(QPalette::HighlightedText, QColor("#171717"));
    palette.setColor(QPalette::ToolTipBase, QColor(surface));
    palette.setColor(QPalette::ToolTipText, QColor(text));
    palette.setColor(QPalette::Disabled, QPalette::Text, QColor("#888888"));
    palette.setColor(QPalette::Disabled, QPalette::ButtonText, QColor("#888888"));
    qApp->setPalette(palette);
    setStyleSheet(QString(
        "QWidget {font-size: 13px;} QLabel#brand {font-size: 24px; font-weight: 600;}"
        "QLabel#pageTitle {font-size: 21px; font-weight: 600;}"
        "QLabel#status, QLabel#activity {color: %5;}"
        "QListWidget {background: %1; border: none;}"
        "QListWidget::item {padding: 12px 8px; border-radius: 5px; margin: 2px 0;}"
        "QListWidget::item:selected {background: %3; color: %2;}"
        "QScrollArea, QStackedWidget {border: none;}"
        "QLineEdit,QPlainTextEdit,QComboBox,QDoubleSpinBox {background: %1; border: 1px solid %3;"
        "border-radius: 5px; padding: 7px; min-height: 20px;}"
        "QPushButton,QToolButton {background: %1; border: 1px solid %3; border-radius: 5px;"
        "padding: 8px 12px;} QPushButton:hover,QToolButton:hover {border-color: %4;}"
        "QPushButton#primary {background: %4; color: #171717; border-color: %4;}"
        "QCheckBox {spacing: 10px; padding: 5px 0;}"
        "QProgressBar {background: %1; border: none; border-radius: 3px; min-height: 8px;}"
        "QProgressBar::chunk {background: %4; border-radius: 3px;}"
    ).arg(surface, text, border, accent, light ? "#666666" : "#aaaaaa"));
}

void Hub::request(QJsonObject messageObject, std::function<void(QJsonObject)> completed) {
    if (busy) return;
    busy = true;
    pages->setEnabled(false);
    saveButton->setEnabled(false);
    reloadButton->setEnabled(false);
    status->setText("Working...");
    auto *process = new QProcess(this);
    auto *timer = new QTimer(process);
    timer->setSingleShot(true);
    auto output = std::make_shared<QByteArray>();
    auto error = std::make_shared<QString>();
    auto done = std::make_shared<bool>(false);
    auto finish = [this, process, timer, output, error, done, completed](int code) {
        if (*done) return;
        *done = true;
        timer->stop();
        output->append(process->readAllStandardOutput());
        QJsonParseError parseError;
        auto document = QJsonDocument::fromJson(*output, &parseError);
        auto response = document.object();
        busy = false;
        pages->setEnabled(true);
        saveButton->setEnabled(ready());
        reloadButton->setEnabled(true);
        if (!error->isEmpty() || parseError.error != QJsonParseError::NoError || code != 0 || !response["ok"].toBool()) {
            auto reason = !error->isEmpty() ? *error : response["error"].toString("Local backend failed. Check the Python runtime installation.");
            status->setText(reason.left(600));
            QMessageBox::warning(this, "Action failed", reason.left(2000));
        } else {
            status->setText(response["message"].toString("Ready"));
            completed(response);
        }
        process->deleteLater();
    };
    connect(process, &QProcess::started, this, [process, messageObject] {
        process->write(QJsonDocument(messageObject).toJson(QJsonDocument::Compact));
        process->closeWriteChannel();
    });
    connect(process, &QProcess::readyReadStandardOutput, this, [process, output, error] {
        output->append(process->readAllStandardOutput());
        if (output->size() > 32 * 1024 * 1024) {
            *error = "Backend response exceeded the size limit.";
            process->kill();
        }
    });
    connect(process, &QProcess::readyReadStandardError, this, [process] { process->readAllStandardError(); });
    connect(process, &QProcess::finished, this, [finish](int code, QProcess::ExitStatus) { finish(code); });
    connect(process, &QProcess::errorOccurred, this, [process, error, finish](QProcess::ProcessError code) {
        *error = process->errorString();
        if (code == QProcess::FailedToStart) finish(-1);
    });
    connect(timer, &QTimer::timeout, this, [process, error] {
        *error = "Backend timed out. Review the service/model before retrying.";
        process->kill();
    });
    process->setProgram(python);
    process->setArguments({"-m", "ai_os.hub_bridge"});
    auto environment = QProcessEnvironment::systemEnvironment();
    environment.insert("AI_OS_HOME", home);
    environment.insert("PYTHONIOENCODING", "utf-8");
    process->setProcessEnvironment(environment);
    process->start();
    timer->start(300000);
}

void Hub::reload() {
    request({{"action", "load"}}, [this](const QJsonObject &document) {
        loadDocument(document);
        ensureCompanion();
    });
}

void Hub::loadDocument(const QJsonObject &document) {
    saved = document["config"].toObject();
    revision = document["revision"].toString();
    protectedKeys = document["protected"].toArray();
    if (fields.isEmpty()) {
        descriptors = document["fields"].toArray();
        addConversation();
        addSettingsPages();
        addNotebook();
        navigation->setCurrentRow(0);
    }
    populate();
    saveButton->setEnabled(true);
    status->setText("Settings loaded");
}

void Hub::addConversation() {
    navigation->addItem(new QListWidgetItem(style()->standardIcon(QStyle::SP_MessageBoxInformation), "Conversation"));
    auto *page = new QWidget(this);
    auto *layout = new QVBoxLayout(page);
    layout->setContentsMargins(0, 0, 0, 0);
    auto *title = new QLabel("Conversation", page);
    title->setObjectName("pageTitle");
    layout->addWidget(title);
    transcript = new QPlainTextEdit(page);
    transcript->setReadOnly(true);
    transcript->setMaximumBlockCount(2000);
    transcript->setAccessibleName("Conversation transcript");
    layout->addWidget(transcript, 1);
    message = new QPlainTextEdit(page);
    message->setFixedHeight(96);
    message->setPlaceholderText("Message REgenOS");
    message->setAccessibleName("Message");
    layout->addWidget(message);
    auto *actions = new QHBoxLayout;
    actions->addWidget(button(this, "Load recent", QStyle::SP_BrowserReload, [this] {
        request({{"action", "history"}}, [this](const QJsonObject &result) {
            transcript->clear();
            for (const auto &item : result["history"].toArray()) {
                auto row = item.toObject();
                transcript->appendPlainText("You\n" + row["user"].toString() + "\n\nREgenOS\n" + row["assistant"].toString() + "\n");
            }
        });
    }));
    actions->addStretch();
    auto *send = button(this, "Send", QStyle::SP_ArrowForward, [this] { sendChat(); });
    send->setObjectName("primary");
    actions->addWidget(send);
    layout->addLayout(actions);
    pages->addWidget(page);
}

void Hub::addSettingsPages() {
    const QStringList names = {"AI connection", "Voice & listening", "Companion", "Appearance", "Memory preferences", "Permissions", "Hardware"};
    const QList<QStyle::StandardPixmap> icons = {QStyle::SP_DriveNetIcon, QStyle::SP_MediaVolume, QStyle::SP_ComputerIcon, QStyle::SP_DesktopIcon, QStyle::SP_DriveHDIcon, QStyle::SP_MessageBoxWarning, QStyle::SP_ComputerIcon};
    for (int index = 0; index < names.size(); ++index) {
        const auto name = names[index];
        navigation->addItem(new QListWidgetItem(style()->standardIcon(icons[index]), name));
        auto *scroll = new QScrollArea(this);
        scroll->setWidgetResizable(true);
        auto *page = new QWidget(scroll);
        auto *layout = new QVBoxLayout(page);
        layout->setContentsMargins(0, 0, 12, 12);
        layout->setSpacing(16);
        auto *title = new QLabel(name, page);
        title->setObjectName("pageTitle");
        layout->addWidget(title);
        auto *form = new QFormLayout;
        form->setHorizontalSpacing(20);
        form->setVerticalSpacing(12);
        form->setRowWrapPolicy(QFormLayout::WrapLongRows);
        form->setFieldGrowthPolicy(QFormLayout::AllNonFixedFieldsGrow);
        layout->addLayout(form);
        for (const auto &item : descriptors) {
            const auto field = item.toObject();
            if (field["page"].toString() != name) continue;
            const auto key = field["key"].toString();
            const auto label = field["label"].toString();
            const auto type = field["type"].toString();
            QWidget *control = nullptr;
            QWidget *rowWidget = nullptr;
            if (type == "bool") {
                control = new QCheckBox(label, page);
            } else if (type == "choice") {
                auto *choice = new QComboBox(page);
                for (auto value : field["choices"].toArray()) choice->addItem(value.toString());
                if (key == "theme") connect(choice, &QComboBox::currentTextChanged, this, &Hub::applyTheme);
                control = choice;
            } else if (type == "number") {
                auto *number = new QDoubleSpinBox(page);
                number->setRange(field["min"].toDouble(), field["max"].toDouble());
                number->setDecimals(field["integer"].toBool() ? 0 : 2);
                number->setSingleStep(field["integer"].toBool() ? 1 : 0.05);
                control = number;
                if (key.startsWith("avatar_")) {
                    rowWidget = new QWidget(page);
                    auto *row = new QHBoxLayout(rowWidget);
                    row->setContentsMargins(0, 0, 0, 0);
                    auto *slider = new QSlider(Qt::Horizontal, rowWidget);
                    slider->setRange(int(field["min"].toDouble()), int(field["max"].toDouble()));
                    slider->setAccessibleName(label);
                    connect(slider, &QSlider::valueChanged, number, &QDoubleSpinBox::setValue);
                    connect(number, &QDoubleSpinBox::valueChanged, slider, [slider](double value) { slider->setValue(int(value)); });
                    row->addWidget(slider, 1);
                    number->setFixedWidth(80);
                    row->addWidget(number);
                }
            } else if (type == "lines") {
                auto *lines = new QPlainTextEdit(page);
                lines->setFixedHeight(96);
                control = lines;
            } else {
                auto *edit = new QLineEdit(page);
                edit->setMaxLength(512);
                control = edit;
                if (type == "file" || type == "color") {
                    rowWidget = new QWidget(page);
                    auto *row = new QHBoxLayout(rowWidget);
                    row->setContentsMargins(0, 0, 0, 0);
                    row->addWidget(edit, 1);
                    auto *pick = new QToolButton(rowWidget);
                    pick->setIcon(style()->standardIcon(type == "file" ? QStyle::SP_DirOpenIcon : QStyle::SP_DialogApplyButton));
                    pick->setToolTip("Choose " + label.toLower());
                    connect(pick, &QToolButton::clicked, this, [this, edit, type, label] {
                        if (type == "file") {
                            auto path = QFileDialog::getOpenFileName(this, label, home);
                            if (!path.isEmpty()) edit->setText(path);
                        } else {
                            auto color = QColorDialog::getColor(QColor(edit->text()), this, label);
                            if (color.isValid()) edit->setText(color.name());
                        }
                    });
                    if (type == "color") connect(edit, &QLineEdit::textChanged, pick, [pick](const QString &value) {
                        if (QColor(value).isValid()) pick->setStyleSheet("background: " + QColor(value).name() + ";");
                    });
                    row->addWidget(pick);
                }
            }
            control->setObjectName(key);
            control->setAccessibleName(label);
            fields[key] = control;
            if (type == "bool") form->addRow(control);
            else form->addRow(label, rowWidget ? rowWidget : control);
        }
        if (name == "Hardware") {
            auto *report = new QPlainTextEdit(page);
            report->setObjectName("hardwareReport");
            report->setAccessibleName("Current hardware and inference policy");
            report->setReadOnly(true);
            report->setMinimumHeight(220);
            auto display = [report](QJsonObject reply) {
                report->setPlainText(QString::fromUtf8(QJsonDocument(reply["report"].toObject()).toJson(QJsonDocument::Indented)));
            };
            auto *actions = new QHBoxLayout;
            layout->addWidget(button(this, "Refresh hardware", QStyle::SP_BrowserReload, [this, display] {
                save([this, display] { request({{"action", "hardware"}}, display); });
            }));
            auto *mode = new QComboBox(page);
            mode->setAccessibleName("This computer's compute override");
            mode->addItem("Follow defaults", "inherit");
            mode->addItem("CPU only", "cpu");
            mode->addItem("Ollama automatic", "auto");
            actions->addWidget(mode);
            actions->addWidget(button(this, "Apply to this computer", QStyle::SP_DialogApplyButton, [this, mode, display] {
                if (!confirm("Hardware override", "Replace this computer's hardware override? Drivers and boot settings are not changed.")) return;
                const auto backend = mode->currentData().toString();
                const QJsonObject value = backend == "inherit" ? QJsonObject{} : QJsonObject{{"backend", backend}};
                save([this, value, display] {
                    request({{"action", "hardware_override"}, {"override", value}, {"confirmed", true}}, display);
                });
            }));
            layout->addLayout(actions);
            layout->addWidget(report);
        }
        if (name == "Voice & listening") {
            auto *actions = new QHBoxLayout;
            for (const QString &action : {QString("start"), QString("restart"), QString("stop")}) {
                actions->addWidget(button(this, action == "start" ? "Start listener" : action == "stop" ? "Stop" : "Restart", action == "stop" ? QStyle::SP_MediaStop : QStyle::SP_MediaPlay, [this, action] {
                    auto run = [this, action] { request({{"action", "service"}, {"command", action}}, [](QJsonObject) {}); };
                    if (action == "stop") run(); else save(run);
                }));
            }
            layout->addLayout(actions);
            layout->addWidget(button(this, "Test voice", QStyle::SP_MediaVolume, [this] {
                save([this] { request({{"action", "speech_test"}}, [](QJsonObject) {}); });
            }));
        }
        if (name == "Appearance") layout->addWidget(button(this, "Apply desktop appearance", QStyle::SP_DialogApplyButton, [this] {
            if (confirm("Desktop appearance", "Apply saved appearance preferences to your desktop files? Existing files are backed up."))
                save([this] { request({{"action", "appearance"}, {"confirmed", true}}, [](QJsonObject) {}); });
        }));
        if (name == "Companion") {
            auto *live = new QFormLayout;
            for (const QString &emotion : {QString("joy"), QString("curiosity"), QString("focus"), QString("calm"), QString("concern"), QString("energy")}) {
                auto *bar = new QProgressBar(page);
                bar->setRange(0, 100);
                bar->setTextVisible(false);
                bar->setAccessibleName("Live " + emotion);
                emotions[emotion] = bar;
                live->addRow(emotion, bar);
            }
            layout->addLayout(live);
        }
        layout->addStretch();
        scroll->setWidget(page);
        pages->addWidget(scroll);
    }
}

void Hub::populate() {
    for (auto it = fields.begin(); it != fields.end(); ++it) {
        const auto value = fieldValue(saved, it.key());
        auto *control = it.value();
        if (auto *check = qobject_cast<QCheckBox *>(control)) check->setChecked(value.toBool());
        else if (auto *choice = qobject_cast<QComboBox *>(control)) choice->setCurrentText(value.toString());
        else if (auto *number = qobject_cast<QDoubleSpinBox *>(control)) number->setValue(value.toDouble());
        else if (auto *lines = qobject_cast<QPlainTextEdit *>(control)) {
            QStringList values;
            for (auto host : value.toArray()) values << host.toString();
            lines->setPlainText(values.join('\n'));
        } else if (auto *edit = qobject_cast<QLineEdit *>(control)) edit->setText(value.toString());
    }
    applyTheme(saved["theme"].toString("graphite"));
    const auto branding = saved["branding"].toObject();
    auto name = branding["brand_name"].toString("REgenOS");
    brand->setText(fontMetrics().elidedText(name, Qt::ElideRight, 400));
    setWindowTitle(name + " Hub");
    auto logo = branding["logo_path"].toString();
    if (QFile::exists(logo)) setWindowIcon(QIcon(logo));
}

QJsonObject Hub::collected() const {
    auto result = saved;
    for (auto it = fields.begin(); it != fields.end(); ++it) {
        auto *control = it.value();
        QJsonValue value;
        if (auto *check = qobject_cast<QCheckBox *>(control)) value = check->isChecked();
        else if (auto *choice = qobject_cast<QComboBox *>(control)) value = choice->currentText();
        else if (auto *number = qobject_cast<QDoubleSpinBox *>(control)) value = number->value();
        else if (auto *lines = qobject_cast<QPlainTextEdit *>(control)) {
            QJsonArray values;
            for (auto line : lines->toPlainText().split('\n')) if (!line.trimmed().isEmpty()) values.append(line.trimmed());
            value = values;
        } else if (auto *edit = qobject_cast<QLineEdit *>(control)) value = edit->text();
        const auto parts = it.key().split('.');
        if (parts.size() == 2) {
            auto nested = result[parts[0]].toObject();
            nested[parts[1]] = value;
            result[parts[0]] = nested;
        } else result[it.key()] = value;
    }
    return result;
}

bool Hub::confirm(const QString &title, const QString &question) {
    return QMessageBox::question(this, title, question, QMessageBox::Yes | QMessageBox::Cancel, QMessageBox::Cancel) == QMessageBox::Yes;
}

void Hub::save(std::function<void()> after) {
    if (!ready() || busy) return;
    const auto values = collected();
    QJsonObject changes;
    for (auto it = values.begin(); it != values.end(); ++it) if (saved[it.key()] != it.value()) changes[it.key()] = it.value();
    QStringList protectedNames;
    for (auto key : protectedKeys) if (changes.contains(key.toString())) protectedNames << key.toString();
    bool confirmed = false;
    if (saved["sandbox_lock_settings"].toBool() && !protectedNames.isEmpty()) {
        confirmed = confirm("Protected settings", "Approve changes to: " + protectedNames.join(", ") + "?");
        if (!confirmed) return;
    }
    request({{"action", "save"}, {"changes", changes}, {"revision", revision}, {"confirmed", confirmed}}, [this, after](const QJsonObject &result) {
        saved = result["config"].toObject();
        revision = result["revision"].toString();
        populate();
        ensureCompanion();
        status->setText("Saved. Restart the listener to apply voice changes.");
        if (after) after();
    });
}

void Hub::sendChat() {
    const auto text = message->toPlainText().trimmed();
    if (text.isEmpty()) return;
    if (text.size() > 8000) { status->setText("Message exceeds 8000 characters."); return; }
    if (collected() != saved) { status->setText("Save or reload settings before sending a message."); return; }
    request({{"action", "chat"}, {"text", text}}, [this, text](const QJsonObject &result) {
        transcript->appendPlainText("You\n" + text + "\n\nREgenOS\n" + replyText(result["response"].toObject()) + "\n");
        message->clear();
        const auto response = result["response"].toObject();
        if (saved["speech_enabled"].toBool() && response["type"].toString() == "text")
            request({{"action", "speech_text"}, {"text", response["content"]}}, [](QJsonObject) {});
    });
}

void Hub::refreshActivity() {
    QFile file(QDir(home).filePath("run/avatar_state.json"));
    QJsonObject state;
    if (file.open(QIODevice::ReadOnly) && file.size() <= 16384)
        state = QJsonDocument::fromJson(file.readAll()).object();
    const double age = QDateTime::currentMSecsSinceEpoch() / 1000.0 - state["updated_at"].toDouble();
    const auto phase = state["phase"].toString();
    if (age < -5 || age > ((phase == "reply" || phase == "error") ? 15 : 180)) state = {};
    activity->setText(state["phase"].toString("idle"));
    auto levels = state["emotions"].toObject();
    const auto baseline = saved["avatar_emotions"].toObject();
    for (auto it = emotions.begin(); it != emotions.end(); ++it) {
        const double base = baseline[it.key()].toDouble();
        const double target = levels.contains(it.key()) ? levels[it.key()].toDouble() : base;
        it.value()->setValue(qBound(0, qRound(base + (target - base) * saved["avatar_reactivity"].toDouble(75) / 100), 100));
    }
}

void Hub::ensureCompanion() {
    if (!saved["avatar_enabled"].toBool() || qEnvironmentVariableIsSet("REGENOS_HUB_NO_COMPANION")) return;
    QProcess process;
    process.setProgram(python);
    process.setArguments({"-m", "ai_os.avatar_overlay"});
    auto env = QProcessEnvironment::systemEnvironment();
    env.insert("AI_OS_HOME", home);
    process.setProcessEnvironment(env);
    process.startDetached();
}

void Hub::closeEvent(QCloseEvent *event) {
    if (busy) {
        status->setText("Wait for the current action to finish before closing.");
        event->ignore();
    } else if (collected() != saved && !confirm("Unsaved settings", "Discard unsaved settings and close?")) {
        event->ignore();
    } else if (ready() && !discardNoteChanges()) event->ignore();
    else event->accept();
}

bool Hub::discardNoteChanges() {
    if (noteTitle->text() == originalNoteTitle && noteBody->toPlainText() == originalNoteBody) return true;
    return confirm("Unsaved context note", "Discard unsaved context note changes?");
}

void Hub::addNotebook() {
    navigation->addItem(new QListWidgetItem(style()->standardIcon(QStyle::SP_FileDialogDetailedView), "Context notebook"));
    auto *page = new QWidget(this);
    auto *layout = new QVBoxLayout(page);
    layout->setContentsMargins(0, 0, 0, 0);
    auto *title = new QLabel("Context notebook", page);
    title->setObjectName("pageTitle");
    layout->addWidget(title);
    noteList = new QListWidget(page);
    noteList->setFixedHeight(150);
    layout->addWidget(noteList);
    noteTitle = new QLineEdit(page);
    noteTitle->setMaxLength(120);
    noteTitle->setPlaceholderText("Note title");
    noteTitle->setAccessibleName("Note title");
    layout->addWidget(noteTitle);
    noteBody = new QPlainTextEdit(page);
    noteBody->setAccessibleName("Context note");
    layout->addWidget(noteBody, 1);
    connect(noteList, &QListWidget::currentRowChanged, this, [this](int index) {
        if (index < 0 || index >= notes.size()) return;
        if (!discardNoteChanges()) {
            QSignalBlocker blocker(noteList);
            noteList->setCurrentRow(selectedNoteRow);
            return;
        }
        const auto note = notes[index].toObject();
        noteId = note["id"].toInt();
        selectedNoteRow = index;
        originalNoteTitle = note["title"].toString();
        originalNoteBody = note["body"].toString();
        noteTitle->setText(originalNoteTitle);
        noteBody->setPlainText(originalNoteBody);
    });
    auto *actions = new QHBoxLayout;
    actions->addWidget(button(this, "Refresh", QStyle::SP_BrowserReload, [this] { refreshNotes(); }));
    actions->addWidget(button(this, "New", QStyle::SP_FileIcon, [this] {
        if (!discardNoteChanges()) return;
        originalNoteTitle.clear(); originalNoteBody.clear(); selectedNoteRow = -1;
        noteId = -1; noteList->setCurrentRow(-1); noteTitle->clear(); noteBody->clear();
    }));
    actions->addWidget(button(this, "Save note", QStyle::SP_DialogSaveButton, [this] {
        QJsonObject data{{"action", "put_note"}, {"title", noteTitle->text()}, {"body", noteBody->toPlainText()}};
        if (noteId >= 0) data["id"] = noteId;
        request(data, [this](QJsonObject result) { showNotes(result); });
    }));
    actions->addWidget(button(this, "Delete", QStyle::SP_TrashIcon, [this] {
        if (noteId >= 0 && confirm("Delete note", "Delete this saved context note?"))
            request({{"action", "delete_note"}, {"id", noteId}, {"confirmed", true}}, [this](QJsonObject result) { showNotes(result); });
    }));
    layout->addLayout(actions);
    auto *files = new QHBoxLayout;
    files->addWidget(button(this, "Import", QStyle::SP_DialogOpenButton, [this] {
        if (!discardNoteChanges()) return;
        auto path = QFileDialog::getOpenFileName(this, "Import context", home, "Context (*.txt *.md *.json)");
        if (path.isEmpty()) return;
        QFile file(path);
        if (!file.open(QIODevice::ReadOnly) || file.size() > 16 * 1024 * 1024) { status->setText("Cannot read file, or file exceeds 16 MiB."); return; }
        const auto bytes = file.readAll();
        if (path.endsWith(".json", Qt::CaseInsensitive)) {
            auto document = QJsonDocument::fromJson(bytes);
            if (!document.isArray()) { status->setText("Expected a JSON array of title/body notes."); return; }
            if (confirm("Import notes", "Add these context notes to your local notebook?"))
                request({{"action", "import_notes"}, {"notes", document.array()}, {"confirmed", true}}, [this](QJsonObject result) { showNotes(result); });
        } else {
            const auto text = QString::fromUtf8(bytes);
            if (text.size() > 8192) { status->setText("Text notes are limited to 8192 characters."); return; }
            noteId = -1;
            originalNoteTitle.clear(); originalNoteBody.clear(); selectedNoteRow = -1;
            noteTitle->setText(QFileInfo(path).completeBaseName().left(120));
            noteBody->setPlainText(text);
            status->setText("Imported into editor. Save note to retain it.");
        }
    }));
    files->addWidget(button(this, "Export", QStyle::SP_DialogSaveButton, [this] {
        auto path = QFileDialog::getSaveFileName(this, "Export context notes", home + "/context-notes.json", "JSON (*.json)");
        if (path.isEmpty()) return;
        request({{"action", "notes"}}, [this, path](QJsonObject result) {
            QSaveFile file(path);
            auto bytes = QJsonDocument(result["notes"].toArray()).toJson();
            if (!file.open(QIODevice::WriteOnly) || file.write(bytes) != bytes.size() || !file.commit())
                status->setText("Could not export notes.");
            else status->setText("Context notes exported. Keep this file private.");
        });
    }));
    files->addWidget(button(this, "Clear conversations", QStyle::SP_TrashIcon, [this] {
        if (confirm("Clear conversations", "Delete stored conversation history? Context notes remain. Legacy event logs and backups are not erased."))
            request({{"action", "clear_history"}, {"confirmed", true}}, [this](QJsonObject) {
                transcript->clear(); status->setText("Stored conversation history cleared.");
            });
    }));
    layout->addLayout(files);
    pages->addWidget(page);
    connect(navigation, &QListWidget::currentTextChanged, this, [this](const QString &text) {
        if (text == "Context notebook" && !busy) refreshNotes();
    });
}

void Hub::refreshNotes() {
    if (!discardNoteChanges()) return;
    request({{"action", "notes"}}, [this](QJsonObject result) { showNotes(result); });
}

void Hub::showNotes(const QJsonObject &result) {
    QSignalBlocker blocker(noteList);
    originalNoteTitle.clear(); originalNoteBody.clear(); selectedNoteRow = -1;
    notes = result["notes"].toArray();
    noteList->clear();
    for (auto item : notes) noteList->addItem(item.toObject()["title"].toString());
    noteId = -1;
    noteTitle->clear();
    noteBody->clear();
    status->setText(QString("%1 local context notes").arg(notes.size()));
}
