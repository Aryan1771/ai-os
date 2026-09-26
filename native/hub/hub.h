#pragma once

#include <QJsonArray>
#include <QJsonObject>
#include <QMainWindow>
#include <QMap>
#include <functional>

class QLabel;
class QListWidget;
class QStackedWidget;
class QPlainTextEdit;
class QLineEdit;
class QPushButton;
class QProcess;
class QProgressBar;

class Hub : public QMainWindow {
public:
    explicit Hub(QString python, QString home, bool connectBackend = true);
    void loadDocument(const QJsonObject &document);
    QJsonObject collected() const;
    void applyTheme(const QString &name);
    void request(QJsonObject message, std::function<void(QJsonObject)> completed);
    bool ready() const { return !saved.isEmpty(); }
protected:
    void closeEvent(QCloseEvent *event) override;
private:
    QString python, home, revision;
    QJsonObject saved;
    QJsonArray protectedKeys, descriptors, notes;
    QMap<QString, QWidget *> fields;
    QMap<QString, QProgressBar *> emotions;
    QListWidget *navigation, *noteList;
    QStackedWidget *pages;
    QLabel *status, *activity, *brand;
    QPlainTextEdit *transcript, *message, *noteBody;
    QLineEdit *noteTitle;
    QPushButton *saveButton, *reloadButton;
    bool busy = false;
    int noteId = -1;
    int selectedNoteRow = -1;
    QString originalNoteTitle, originalNoteBody;
    bool discardNoteChanges();
    void reload();
    void save(std::function<void()> after = {});
    void populate();
    void refreshActivity();
    void refreshNotes();
    void showNotes(const QJsonObject &result);
    void sendChat();
    void ensureCompanion();
    void addConversation();
    void addNotebook();
    void addSettingsPages();
    bool confirm(const QString &title, const QString &question);
};
