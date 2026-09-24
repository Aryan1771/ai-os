# Calamares Graphical Installer Work

Calamares is the candidate installer for an Ubuntu-style graphical setup wizard. This directory records the integration boundary; REGENOS does not claim to ship a tested installer configuration yet. Archiso builds live media. Calamares requires a packaged build plus distribution configuration and installation modules.

## Build And Integrate In This Order

1. Choose and test the live desktop/session first. The current desktop prototype uses Hyprland; Calamares must run inside that graphical session with its Qt dependencies.
2. Package Calamares and its required modules for the exact Arch package snapshot used by the ISO. Prefer a signed project repository or a reviewed PKGBUILD in a clean chroot. Do not download and execute an unreviewed installer binary during ISO build.
3. Add distribution configuration under `airootfs/etc/calamares/`: `settings.conf`, module configs, and `branding/regenos/`. Keep the module sequence synchronized with installed Calamares modules.
4. Define the target system package set and installation method. Verify the installed bootloader, initramfs, user, locale, network, GPU driver, and AI-OS service in the target root.
5. Start the installer from a desktop launcher that invokes `pkexec calamares`; test authorization and cancellation behavior.
6. Build with `mkarchiso`, then test UEFI and BIOS modes as supported, clean installs, manual partitions, full-disk erase in a disposable VM, and failed-install recovery.

## References

- [Archiso profile structure](https://github.com/archlinux/archiso/blob/master/docs/README.profile.rst)
- [Calamares user guide and modules](https://calamares.io/docs/users-guide/)
- [Calamares deployment configuration](https://github.com/calamares/calamares/wiki/Deploy-Configuration)

Do not add Calamares to the Archiso package list until the chosen package source is configured and reproducible. Upstream module configuration changes over time, so use examples from the exact packaged version and validate them in the built ISO.
