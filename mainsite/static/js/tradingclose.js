/*
    WebSocket communication system 2.2
    The future is now, noooom!
*/

class TradingNotifier {
    constructor(trading_ws_url, me, they) {
        this.trading_ws = new WebSocket(trading_ws_url)

        this.me = me
        this.they = they

        this.states = ["ACCEPTED", "CANCELLED", "COMPLETED", "FAILED"]

        // connect the socket
        this.trading_socket_connect()
    }

    async trading_socket_connect() {
        var _self = this

        _self.trading_ws.onopen = async function open() {
            console.log('WebSockets connection created.')
            // on websocket open, send the START action.
            await _self.trading_ws.send(JSON.stringify({ action: "HELLO" }))
        }

        _self.trading_ws.onclose = async function (evt) {
            console.log('Socket is closed. Reconnect will be attempted in 1 second.', evt.reason)
            setTimeout(async function () { await _self.trading_socket_connect() }, 1000)
        }

        // Sending the info about the room
        _self.trading_ws.onmessage = async function (evt) {
            // On getting the message from the server
            // Do the appropriate steps on each action.
            console.log("[RAW DATA]", evt.data)
            const { identifier, action, message, item } = JSON.parse(evt.data)

            if (_self.states.includes(action)) location.reload()
        }

        if (_self.trading_ws.readyState == WebSocket.OPEN) await _self.trading_ws.onopen()
    }

    async _update_offer(e) {
        var _self = this

        const buttons = document.querySelectorAll("button[data-choice]")
        buttons.forEach(b => b.disabled = true)

        const response = await _self.#_process_choice(e.dataset.choice)
        console.log("[DEBUG REQ RESPONSE]", response)

        if (response.status) {
            location.reload()
        } else {
            buttons.forEach(b => b.disabled = false)
            console.error(response.error)
        }
    }

    async #_process_choice(choice) {
        const headers = new Headers({ 'Content-Type': 'application/json', })
        const request = await fetch(location.pathname.replace('closed/','resolve/'), {
          method: 'POST',
          headers: headers,
          cache: 'no-cache',
          credentials: 'same-origin',
          body: JSON.stringify({ choice: choice }),
        })

        const response = await request.json()
        console.log("[DEBUG UPDATE RESPONSE]", response)
        return response
    }
}
