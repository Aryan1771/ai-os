# Phase 5: Hyprland Desktop

Do this only after the terminal daemon, audio, and systemd user service work reliably. Hyprland is intentionally absent from the default AI-OS runtime path.

```bash
cd ~/src/ai-os
bash install/ai-os-install.sh desktop
```

Copy the rest of your normal Hyprland configuration into `~/.config/hypr/hyprland.conf`. Add only these AI-OS related lines after verifying the wallpaper files exist:

```ini
exec-once = hyprpaper
exec-once = waybar
```

Install original branding before launching Hyprpaper or Hyprlock:

```bash
sudo install -d -m 0755 /usr/share/ai-os/wallpapers /usr/share/ai-os/logos
sudo install -m 0644 branding/wallpapers/default.png /usr/share/ai-os/wallpapers/default.png
sudo install -m 0644 branding/wallpapers/lockscreen.png /usr/share/ai-os/wallpapers/lockscreen.png
```

Test the desktop components individually:

```bash
hyprpaper &
hyprlock
hyprctl clients -j
```

Only then edit `~/.ai_os/config.json` and set `hyprland_enabled` to `true`. UI typing remains consent-gated inside the daemon. `ydotool` requires its companion daemon and appropriate `/dev/uinput` access; verify that independently before trusting it with any automation.
