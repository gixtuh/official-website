sudo pacman -Sy git base-devel unzip
git clone https://aur.archlinux.org/yay.git
cd yay
makepkg -si
cd ..
wget https://gixtuh.vercel.app/files/hyprland-dotfiles.zip
unzip hyprland-dotfiles.zip -d dotfiles
cd dotfiles
./installer.sh