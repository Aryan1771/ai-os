# Phase 5: Hyprland Desktop

Do this only after the terminal daemon, audio, and systemd user service work reliably. Hyprland is intentionally absent from the default REgenOS runtime path.

```bash
cd ~/src/ai-os
bash install/ai-os-install.sh desktop
```

Copy the rest of your normal Hyprland configuration into `~/.config/hypr/hyprland.conf`. Add only these AI-OS related lines after verifying the wallpaper files exist:

```ini
exec-once = hyprpaper
exec-once = waybar
source = ~/.config/hypr/regenos-bindings.conf
source = ~/.config/hypr/regenos-companion.conf
source = ~/.config/hypr/regenos-cursor.conf
exec-once = ~/.ai_os/venv/bin/regenos-companion
```

The bindings use the Super key (the Windows-logo key on most laptops): Super+Space opens the app launcher; Super+Enter opens Kitty; Super+E opens Thunar; Super+A opens REgenOS Settings; Super+R starts the AI daemon, Super+Shift+R restarts it, and Super+Ctrl+R stops it; Super+V toggles mute; Super+Up/Down changes volume; Super+Shift+Up/Down changes brightness; Super+L locks; Super+Shift+Q closes the active window. These are Hyprland bindings, not global shortcuts for a TTY or another desktop. Resolve conflicts with existing bindings before sourcing the file.

Install original branding before launching Hyprpaper or Hyprlock:

```bash
sudo install -d -m 0755 /usr/share/regenos/wallpapers /usr/share/regenos/branding
sudo install -m 0644 branding/regenos-mark.svg /usr/share/regenos/branding/regenos-mark.svg
magick branding/wallpapers/default.svg /tmp/regenos-default.png
magick branding/wallpapers/lockscreen.svg /tmp/regenos-lockscreen.png
sudo install -m 0644 /tmp/regenos-default.png /usr/share/regenos/wallpapers/default.png
sudo install -m 0644 /tmp/regenos-lockscreen.png /usr/share/regenos/wallpapers/lockscreen.png
```

Test the desktop components individually:

```bash
hyprpaper &
hyprlock
hyprctl clients -j
```

Only then edit `~/.ai_os/config.json` and set `hyprland_enabled` to `true`. UI typing remains consent-gated inside the daemon. `ydotool` requires its companion daemon and appropriate `/dev/uinput` access; verify that independently before trusting it with any automation. System-level desktop settings and other desktop environments are not replaced by this panel; REgenOS Settings is an additional product control center.
