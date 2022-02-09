
class NotificationWS {
    constructor(general_ws_url) {
      this.general_ws = new WebSocket(general_ws_url)
      this.start()
    }

    async start () {
      if (Notification.permission == "granted") {
        // connect the socket
        await this.general_ws_connect()
      }

      const button = document.querySelector("#notification_button")
      await this.update_notification_status(button, Notification.permission)
    }

    async update_notification_status(button, permission) {
      try {
        if (!button) return false
        const notificationSpan = document.querySelector("#notification_button span")
        if (permission === "granted") {
          notificationSpan.innerText = "Notifications enabled"
          button.disabled = true
        } else if (permission === "denied") {
          notificationSpan.innerText = "Notifications disabled"
          button.disabled = true
        } else {
          notificationSpan.innerText = "Enable notifications"
          button.disabled = false
        }
      } catch(error) {
        // console.error(e)
        if (button) button.disable = false
        console.log("nothing to do", error)
      }
    }

    async ask_permission(e) {
      // event for user interaction
      e.disable = true
      var _self = this

      if (!("Notification" in window)) {
        e.innerText = "Notifications not supported"
      } else {
        if (Notification.permission !== "denied") {
          console.log("requesting permission")
          const permission = await Notification.requestPermission()
          console.log(permission)
          location.reload()
        }
      }

      _self.update_notification_status(e, "Not supported")
    }

    async general_ws_connect() {
        var _self = this

        _self.general_ws.onopen = async function open() {
            console.log('Notifications WS connected.')
        }

        _self.general_ws.onclose = async function (evt) {
            console.log('Notifications Socket is closed. Reconnecting in 1 second.', evt.reason)
            setTimeout(async function () { await _self.general_ws_connect() }, 1000)
        }

        _self.general_ws.onmessage = async function (evt) {
            const {order, title, message, extra} = JSON.parse(evt.data)
            const notif = new Notification(title, { body: message, requireInteraction: true })
            notif.onclick = click => {
                click.preventDefault()
                click.target.close()
                if (extra.url) {
                    if (location.assign) {
                      location.assign(extra.url)
                    } else {
                      location.href = extra.url
                    }
                }
            }
        }

        if (_self.general_ws.readyState == WebSocket.OPEN) await _self.general_ws.onopen()
    }
}


async function search_users(string, csrftoken) {
  const request = new Request('/user/search/', {
    'headers': {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrftoken,
    }
  })

  const data = await fetch(request, {
    method: 'POST',
    cache: 'no-cache',
    mode: 'same-origin',
    body: JSON.stringify({ string: string }),
  })
  return await data.json()
}


document.addEventListener("keypress", evt => {
    let target = evt.target
    if (evt.target.getAttribute("type") != "number") return true
    if (evt.which < 48 || evt.which > 57) evt.preventDefault()
})