-- REgenOS integration for Hyprland 0.55+. Loaded by the user's main Lua config.
local home = os.getenv("HOME")
local python = home .. "/.ai_os/venv/bin/python"
hl.env("XCURSOR_THEME", "REgenOS-Cool")
hl.env("XCURSOR_SIZE", "32")
hl.config({ misc = { disable_hyprland_logo = true } })
hl.on("hyprland.start", function()
    hl.exec_cmd(python .. " -m ai_os.session_start")
    hl.exec_cmd("hyprctl setcursor REgenOS-Cool 32")
end)
hl.bind("SUPER + A", hl.dsp.exec_cmd(python .. " -m ai_os.native_settings"))
hl.bind("SUPER + SHIFT + A", hl.dsp.exec_cmd(python .. " -m ai_os.avatar_overlay"))
hl.bind("SUPER + RETURN", hl.dsp.exec_cmd("kitty"))
hl.bind("SUPER + SPACE", hl.dsp.exec_cmd("wofi --show drun"))
hl.bind("SUPER + L", hl.dsp.exec_cmd("hyprlock"))
hl.bind("SUPER + CTRL + R", hl.dsp.exec_cmd("systemctl --user stop ai-os.service"))
hl.window_rule({
    name = "regenos-companion", match = { class = "^(regenos-companion)$" },
    float = true, pin = true, no_initial_focus = true, decorate = false,
    border_size = 0, no_blur = true, no_shadow = true,
})
