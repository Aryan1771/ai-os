#include "hub.h"
#include <QApplication>
#include <QCheckBox>
#include <QComboBox>
#include <QDoubleSpinBox>
#include <QLineEdit>
#include <QFile>
#include <QJsonDocument>
#include <QPushButton>
#include <QPlainTextEdit>
#include <QTemporaryDir>
#include <QtTest>

class HubTests : public QObject {
    Q_OBJECT
private slots:
    void destroyDuringRequest() {
        const auto python = qEnvironmentVariable("REGENOS_TEST_PYTHON");
        if (python.isEmpty()) QSKIP("Set REGENOS_TEST_PYTHON for process cleanup test");
        QTemporaryDir directory;
        auto *hub = new Hub(python, directory.path(), false);
        hub->request({{"action", "load"}}, [](QJsonObject) {});
        QTest::qWait(10);
        delete hub;
    }
    void realBackendRoundTrip() {
        const auto python = qEnvironmentVariable("REGENOS_TEST_PYTHON");
        if (python.isEmpty()) QSKIP("Set REGENOS_TEST_PYTHON for the real bridge integration test");
        qputenv("REGENOS_HUB_NO_COMPANION", "1");
        QTemporaryDir directory;
        Hub hub(python, directory.path());
        hub.show();
        QTRY_VERIFY_WITH_TIMEOUT(hub.ready(), 15000);
        QVERIFY(hub.findChild<QCheckBox *>("hardware_auto_adapt"));
        QVERIFY(hub.findChild<QComboBox *>("hardware_backend"));
        QVERIFY(hub.findChild<QPlainTextEdit *>("hardwareReport")->isReadOnly());
        hub.findChild<QDoubleSpinBox *>("piper_length_scale")->setValue(1.3);
        auto *save = hub.findChild<QPushButton *>("primary");
        QVERIFY(save);
        save->click();
        QTRY_VERIFY_WITH_TIMEOUT(save->isEnabled(), 15000);
        QFile file(directory.filePath("config.json"));
        QVERIFY(file.open(QIODevice::ReadOnly));
        const auto config = QJsonDocument::fromJson(file.readAll()).object();
        QCOMPARE(config["piper_length_scale"].toDouble(), 1.3);
        QCOMPARE(config["theme"].toString(), "graphite");
        QCOMPARE(hub.collected(), config);
        bool receivedHardware = false;
        QJsonObject hardware;
        hub.request({{"action", "hardware"}}, [&](QJsonObject reply) {
            hardware = reply["report"].toObject();
            receivedHardware = true;
        });
        QTRY_VERIFY_WITH_TIMEOUT(receivedHardware, 20000);
        QVERIFY(hardware.contains("hardware"));
        QVERIFY(hardware["policy"].toObject().contains("reason"));
    }
    void settingsRoundTrip() {
        QTemporaryDir directory;
        Hub hub("unused", directory.path(), false);
        QJsonObject config{{"theme", "graphite"}, {"memory_enabled", true},
                           {"wake_word_threshold", 0.5},
                           {"branding", QJsonObject{{"brand_name", "REgenOS"}}}};
        QJsonArray fields{
            QJsonObject{{"key", "theme"}, {"label", "Theme"}, {"page", "Appearance"}, {"type", "choice"}, {"choices", QJsonArray{"graphite", "light"}}},
            QJsonObject{{"key", "memory_enabled"}, {"label", "Memory"}, {"page", "Memory preferences"}, {"type", "bool"}},
            QJsonObject{{"key", "wake_word_threshold"}, {"label", "Threshold"}, {"page", "Voice & listening"}, {"type", "number"}, {"min", 0}, {"max", 1}},
            QJsonObject{{"key", "branding.brand_name"}, {"label", "Name"}, {"page", "Appearance"}, {"type", "text"}}
        };
        hub.loadDocument({{"config", config}, {"fields", fields}});
        QCOMPARE(hub.collected(), config);
        hub.findChild<QCheckBox *>("memory_enabled")->setChecked(false);
        hub.findChild<QDoubleSpinBox *>("wake_word_threshold")->setValue(0.75);
        hub.findChild<QLineEdit *>("branding.brand_name")->setText("REgenOS Lab");
        QCOMPARE(hub.collected()["memory_enabled"].toBool(), false);
        QCOMPARE(hub.collected()["wake_word_threshold"].toDouble(), 0.75);
        QCOMPARE(hub.collected()["branding"].toObject()["brand_name"].toString(), "REgenOS Lab");
        hub.resize(780, 620);
        hub.show();
        QTest::qWait(50);
        QVERIFY(!hub.grab().isNull());
    }
    void standardDarkPalette() {
        QTemporaryDir directory;
        Hub hub("unused", directory.path(), false);
        QCOMPARE(qApp->palette().color(QPalette::Window), QColor("#202020"));
        QCOMPARE(qApp->palette().color(QPalette::Base), QColor("#2b2b2b"));
        hub.applyTheme("light");
        QVERIFY(qApp->palette().color(QPalette::Window).lightness() > 200);
    }
};
QTEST_MAIN(HubTests)
#include "tests.moc"
