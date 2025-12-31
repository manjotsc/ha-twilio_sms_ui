# Twilio SMS for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/manjotsc/ha-twilio_sms?style=for-the-badge)](https://github.com/manjotsc/ha-twilio_sms/releases)
[![License](https://img.shields.io/github/license/manjotsc/ha-twilio_sms?style=for-the-badge)](LICENSE)

> Send SMS and MMS messages from Home Assistant using Twilio

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 📱 **SMS** | Send text messages to multiple recipients |
| 🖼️ **MMS** | Send images via media URLs |
| 📁 **Local Files** | Auto-converts `/local/` paths to external URLs |
| 🔧 **Templates** | Full Jinja2 support for dynamic content |
| 📞 **Multi-Number** | Use multiple Twilio phone numbers |
| ⚙️ **Config Flow** | Easy UI-based setup |

---

## 📦 Installation

### HACS (Recommended)

1. Open **HACS** in Home Assistant
2. Click **Integrations** → **⋮** → **Custom repositories**
3. Add `https://github.com/manjotsc/ha-twilio_sms` and select **Integration**
4. Search for **Twilio SMS** and install
5. Restart Home Assistant

### Manual

1. Download `custom_components/twilio_sms` folder
2. Copy to `config/custom_components/`
3. Restart Home Assistant

---

## ⚙️ Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration** → Search **Twilio SMS**
3. Enter your credentials:

| Field | Description |
|-------|-------------|
| Account SID | Your Twilio Account SID |
| Auth Token | Your Twilio Auth Token |

> 📍 **Find your credentials:**
> [US](https://console.twilio.com/us1/account/keys-credentials/api-keys) •
> [Australia](https://console.twilio.com/au1/account/keys-credentials/api-keys) •
> [Ireland](https://console.twilio.com/ie1/account/keys-credentials/api-keys)

4. Select phone numbers to use
5. *(Optional)* Enter **External URL** for MMS with local files

---

## 🚀 Usage

### Service: `twilio_sms.send_message`

| Parameter | Required | Description |
|-----------|:--------:|-------------|
| `target` | ✅ | Phone number(s) in E.164 format |
| `message` | ✅ | Message body (supports Jinja2) |
| `from_number` | ✅ | Twilio number to send from |
| `media_url` | ❌ | URL(s) for MMS media |

---

## 📝 Examples

<details>
<summary><b>Basic SMS</b></summary>

```yaml
service: twilio_sms.send_message
data:
  target: "+15551234567"
  message: "Hello from Home Assistant!"
  from_number: "+15559876543"
```
</details>

<details>
<summary><b>Multiple Recipients</b></summary>

```yaml
service: twilio_sms.send_message
data:
  target:
    - "+15551234567"
    - "+15551234568"
  message: "Alert! Motion detected."
  from_number: "+15559876543"
```
</details>

<details>
<summary><b>Jinja2 Templates</b></summary>

```yaml
service: twilio_sms.send_message
data:
  target: "{{ states('input_text.my_phone') }}"
  message: |
    Home Assistant Status:
    Version: {{ state_attr('update.home_assistant_core_update', 'installed_version') }}
    Temperature: {{ states('sensor.temperature') }}°F
    Time: {{ now().strftime('%H:%M') }}
  from_number: "+15559876543"
```
</details>

<details>
<summary><b>MMS with External Image</b></summary>

```yaml
service: twilio_sms.send_message
data:
  target: "+15551234567"
  message: "Check out this image!"
  media_url: "https://example.com/image.jpg"
  from_number: "+15559876543"
```
</details>

<details>
<summary><b>MMS with Camera Snapshot</b></summary>

```yaml
# Save snapshot to /config/www/ folder
- service: camera.snapshot
  target:
    entity_id: camera.front_door
  data:
    filename: /config/www/snapshot.jpg

# Send via MMS (/local/ auto-converts to external URL)
- service: twilio_sms.send_message
  data:
    target: "+15551234567"
    message: "Motion detected at front door!"
    media_url: "/local/snapshot.jpg"
    from_number: "+15559876543"
```
</details>

---

## 🖼️ MMS Media URLs

Twilio fetches media from URLs — they must be **publicly accessible**.

| Type | Usage |
|------|-------|
| **External URL** | Use directly: `https://example.com/image.jpg` |
| **Local File** | Place in `/config/www/`, reference as `/local/filename.jpg` |

> ⚠️ **Local files require:**
> - External URL configured in integration settings
> - Home Assistant accessible from internet (Nabu Casa, reverse proxy, etc.)

**Supported paths:** `/local/`, `/media/`, `/api/`

---

## 🤖 Automation Example

```yaml
automation:
  - alias: "Motion Alert with Photo"
    trigger:
      - platform: state
        entity_id: binary_sensor.front_door_motion
        to: "on"
    action:
      - service: camera.snapshot
        target:
          entity_id: camera.front_door
        data:
          filename: /config/www/motion.jpg
      - delay: "00:00:02"
      - service: twilio_sms.send_message
        data:
          target: "+15551234567"
          message: "🚨 Motion detected at {{ now().strftime('%H:%M:%S') }}"
          media_url: "/local/motion.jpg"
          from_number: "+15559876543"
```

---

## 🔧 Troubleshooting

<details>
<summary><b>Media not sending</b></summary>

- ✅ Configure **External URL** in integration settings
- ✅ Verify URL is accessible from internet
- ✅ Check file exists in `/config/www/`
- ✅ Enable **Debug Logging** in integration options
</details>

<details>
<summary><b>Invalid credentials</b></summary>

- ✅ Verify Account SID and Auth Token from Twilio Console
- ✅ Use main account credentials, not API keys
</details>

<details>
<summary><b>Phone number not found</b></summary>

- ✅ Verify number is active in Twilio account
- ✅ Check messaging is enabled for the number
</details>

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

<p align="center">
  <sub>Built with ❤️ for the Home Assistant community</sub>
</p>
