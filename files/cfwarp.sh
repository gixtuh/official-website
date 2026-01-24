echo "linxux bedian cfwarp installer official thing lolol"
curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg | sudo gpg --yes --dearmor --output /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ $(. /etc/os-release && printf $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/cloudflare-client.list
sudo apt install cloudflare-warp
