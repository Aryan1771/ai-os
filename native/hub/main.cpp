#include "hub.h"
#include <QApplication>
#include <QCommandLineParser>
#include <QDir>
#include <QLocalServer>
#include <QLocalSocket>
#include <QLockFile>
#include <QMessageBox>
#include <QTimer>
#include <QListWidget>
#include <QFontDatabase>

int main(int argc, char **argv) {
    QApplication app(argc, argv);
    app.setApplicationName("regenos-hub");
    app.setDesktopFileName("regenos-settings");
    app.setStyle("Fusion");
#ifdef Q_OS_WIN
    QFontDatabase::addApplicationFont(qEnvironmentVariable("WINDIR", "C:/Windows") + "/Fonts/segoeui.ttf");
    app.setFont(QFont("Segoe UI", 10));
#else
    app.setFont(QFont("Noto Sans", 10));
#endif
    QCommandLineParser parser;
    parser.addHelpOption();
    parser.addOption({"python", "Python runtime interpreter", "path"});
    parser.addOption({"screenshot", "Save a native screenshot and exit", "path"});
    parser.addOption({"page", "Screenshot page index", "index", "1"});
    parser.addOption({"compact", "Use the compact window size"});
    parser.process(app);
    const auto home = qEnvironmentVariable("AI_OS_HOME", QDir::homePath() + "/.ai_os");
    auto python = parser.value("python");
    if (python.isEmpty()) python = home + "/venv/bin/python";
    QDir().mkpath(home + "/run");
    const auto socketName = home + "/run/regenos-hub.sock";
    QLockFile lock(home + "/run/regenos-hub.lock");
    lock.setStaleLockTime(0);
    if (!lock.tryLock(0)) {
        QLocalSocket socket;
        socket.connectToServer(socketName);
        if (socket.waitForConnected(1000)) { socket.write("show"); socket.waitForBytesWritten(1000); }
        return 0;
    }
    QLocalServer::removeServer(socketName);
    QLocalServer server;
    server.setSocketOptions(QLocalServer::UserAccessOption);
    if (!server.listen(socketName)) {
        QMessageBox::critical(nullptr, "REgenOS Hub", server.errorString());
        return 1;
    }
    Hub hub(python, home);
    if (parser.isSet("compact")) hub.resize(780, 620);
    QObject::connect(&server, &QLocalServer::newConnection, &hub, [&] {
        while (auto *socket = server.nextPendingConnection()) {
            socket->close(); socket->deleteLater();
            hub.showNormal(); hub.raise(); hub.activateWindow();
        }
    });
    hub.show();
    if (parser.isSet("screenshot")) {
        auto *timer = new QTimer(&hub);
        QObject::connect(timer, &QTimer::timeout, &hub, [&, timer] {
            if (!hub.ready()) return;
            timer->stop();
            hub.findChild<QListWidget *>("navigation")->setCurrentRow(parser.value("page").toInt());
            QTimer::singleShot(700, &hub, [&] {
                app.exit(hub.grab().save(parser.value("screenshot")) ? 0 : 1);
            });
        });
        timer->start(200);
        QTimer::singleShot(20000, &app, [&] { app.exit(2); });
    }
    return app.exec();
}
