/*
    WebSocket communication system 2.2
    The future is now, moooom!
*/

class TradingNotifier {
    constructor(trading_ws_url, me, they) {
        this.trading_ws_url = trading_ws_url
        this.trading_ws = new WebSocket(this.trading_ws_url)

        this.me = me
        this.they = they

        this.definitive_actions = ["RESERVED", "FAILED"]
        this.pinging = false

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
            setTimeout(async function () {
                _self.trading_ws = new WebSocket(_self.trading_ws_url)
                await _self.trading_socket_connect()
            }, 1000)
        }

        // Sending the info about the room
        _self.trading_ws.onmessage = async function (evt) {
            // On getting the message from the server
            // Do the appropriate steps on each action.
            console.log("[RAW DATA]", evt.data)
            const { identifier, action, message, item } = JSON.parse(evt.data)

            if (identifier == _self.they) {
                await _self.#_update_their_local_bundle(action, item)
            } else if (identifier == _self.me) {
                console.log("update my local stuff", action)
            } else {
                if (_self.definitive_actions.includes(action)) { location.reload() }
            }
        }

        if (_self.trading_ws.readyState == WebSocket.OPEN) await _self.trading_ws.onopen()
    }


    // add items/assets to the bundle
    async _add(e) {
        var _self = this
        // setup variables
        const button = e
        button.disabled = true

        const original_entry = e.parentNode.parentNode.parentNode.parentNode

        const { id, type, name, image, details, can_recycle } = original_entry.dataset
        const amount = parseInt(original_entry.dataset.amount)

        // get value
        var input = original_entry.querySelector("input")
        input.disabled = true
        const value = await _self._get_input_amount(input)

        if (!value) {
            button.disabled = false
            input.disabled = false
            return false
        }

        // check if bundle has the item already
        var bundle = document.querySelector("#my_bundle")
        var in_bundle_entry = bundle.querySelector(`[data-id="${id}"][data-type="${type}"]`)
        // update new amount if
        var new_total = in_bundle_entry ? parseInt(in_bundle_entry.dataset.amount) + value : value

        // update database before anything else
        const response = await _self.#_update_my_remote_bundle('ADD', {
            id: id,
            type: type,
            name: name,
            amount: new_total,
            image: image,
            details: details && details != 'None' && details != 'undefined' ? details : '',
            can_recycle: parseInt(can_recycle) || 0,
        })

        if (!response.status) {
            button.disabled = false
            input.disabled = false
            return false
        }

        if (in_bundle_entry) {
            // update existing content in bundle
            in_bundle_entry.dataset.amount = new_total
            // update view
            var in_counter = in_bundle_entry.querySelector("[data-name='count']")
            in_counter.innerText = new_total
        } else {
            // create new entry in the bundle
            var new_bundle_entry = document.createElement("div")
            new_bundle_entry.classList.add("card")

            new_bundle_entry.dataset.id = id
            new_bundle_entry.dataset.type = type
            new_bundle_entry.dataset.name = name
            new_bundle_entry.dataset.image = image
            new_bundle_entry.dataset.details = details && details != 'None' && details != 'undefined' ? details : ''
            new_bundle_entry.dataset.can_recycle = parseInt(can_recycle)
            new_bundle_entry.dataset.amount = new_total

            let recycle_msg = parseInt(can_recycle) ? "<p>Recyclable</p>" : ""

            const imagetag = original_entry.querySelector('[data-mkt-role="image"]').innerHTML
            const nametag = original_entry.querySelector('[data-mkt-role="name"]').outerHTML

            // this is the new entry in MY bundle
            new_bundle_entry.innerHTML = `
                <div class="medias" data-mkt-role="image">
                    ${imagetag}
                </div>

                <div class="item_list_content">
                    <div class="card-body-left">
                        <div class="item-number">
                            <div>
                                <p data-name="count">${new_total}</p>
                            </div>
                        </div>
                        <div class="item-detail">
                            <div>
                                ${nametag}${recycle_msg}
                            </div>
                        </div>
                    </div>
                    <div class="card-body-right">
                        <div class="item-btn">
                            <button class="dashboard-btn" onclick="ts._remove(this)">
                                <span>Remove</span>
                            </button>
                        </div>
                    </div>
                </div>`

            bundle.append(new_bundle_entry)
            _self.#_refresh_popovers()
        }

        // update item/asset count in inventory
        original_entry.dataset.amount = parseInt(amount) - value
        var counter = original_entry.querySelector("[data-name='count']")
        counter.innerText = original_entry.dataset.amount

        // restore value input
        input.value = 0
        input.max = original_entry.dataset.amount

        // remove entry from inventory if needed
        if (parseInt(counter.innerText) < 1) original_entry.remove()
        // reset blocked elements
        if (button) button.disabled = false
        if (input) input.disabled = false

        _self._reset_submit()
    }

    // remove items from bundle
    async _remove(e) {
        // remove item from database
        var _self = this
        // setup variables
        const bundle_entry = e.parentNode.parentNode.parentNode.parentNode
        const button = e
        button.disabled = true

        const response = await _self.#_update_my_remote_bundle('REMOVE', bundle_entry.dataset)

        if (response.status) {
            _self.#_perform_element_removal(bundle_entry)
            _self._reset_submit()
        }

        if (button) button.disabled = false
    }

    async _reset_submit() {
        const submit_button = document.getElementById("submit_button")
        submit_button.disabled = false
    }

    async _add_bits(e) {
        var _self = this
        e.disabled = true

        const bits_input = document.querySelector("#bits")
        bits_input.disabled = true
        const total_bits_display = document.querySelector("#total_bits")
        const my_bits = document.querySelector("#my_bits")
        const amount = await _self._get_input_amount(bits_input)

        if (!amount) {
            e.disabled = false
            bits_input.disabled = false
            return false
        }

        const difference = parseInt(total_bits_display.innerText) - amount
        const new_total = parseInt(my_bits.innerText) + amount

        let result = await _self.#_update_my_remote_bundle('UPDATE_BITS', Object.assign({}, { amount: new_total }))

        if (!result.status) {
            e.disabled = false
            bits_input.disabled = false
            return false
        }

        my_bits.dataset.amount = new_total
        my_bits.innerText = new_total

        total_bits_display.dataset.amount = difference
        total_bits_display.innerText = difference

        bits_input.value = 0
        bits_input.max = difference

        e.disabled = false
        bits_input.disabled = false
        _self._reset_submit()
    }

    async _get_input_amount(input) {
        const amount = parseInt(input.value)

        if (!amount) return false
        if (amount > parseInt(input.max)) return false
        if (amount < 0) return false

        return amount
    }

    async _flush_bits(e) {
        var _self = this
        e.disabled = true

        const bits_input = document.querySelector("#bits")
        bits_input.disabled = true

        const total_bits_display = document.querySelector("#total_bits") // bits in my wallet
        const my_bits = document.querySelector("#my_bits") // bundle bits
        const amount = parseInt(my_bits.dataset.amount)

        if (!amount || amount < 0) {
            e.disabled = false
            bits_input.disabled = false
            return false
        }

        let result = await _self.#_update_my_remote_bundle('UPDATE_BITS', { amount: 0 })

        if (!result.status) {
            e.disabled = false
            bits_input.disabled = false
            return false
        }

        const new_total = parseInt(total_bits_display.innerText) + amount

        my_bits.dataset.amount = 0
        my_bits.innerText = 0

        bits_input.max = new_total

        total_bits_display.dataset.amount = new_total
        total_bits_display.innerText = new_total

        bits_input.disabled = false
        e.disabled = false
        _self._reset_submit()
    }

    async _submit_offer(e) {
        let response
        try {
            var _self = this
            event.preventDefault()
            e.disabled = true
            const headers = new Headers({ 'Content-Type': 'application/json', })
            const request = await fetch(location.pathname+'submit/', {
              method: 'POST',
              headers: headers,
              cache: 'no-cache',
              credentials: 'same-origin',
              body: JSON.stringify({
                action: "SUBMIT",
                data: { identifier: _self.me }
              }),
            })

            response = await request.json()
            console.log(response)
            if (response.error && response.error == 'OFFER_EXPIRED') {
                location.reload()
            }
        } catch (error) {
            console.log(error)
            response = {}
        }
        if (!response.status) e.disabled = false
    }


    // remove from my bundle and return item to inventory
    async #_perform_element_removal(entry) {
        // get dataset
        var _self = this
        const { id, type, name, image, details, can_recycle } = entry.dataset
        const amount = parseInt(entry.dataset.amount)

        // check if item is still in inventory
        var inventory = document.querySelector(`[data-inventory_type="${type}"]`)
        var inventory_entry = inventory.querySelector(`[data-id="${id}"][data-type="${type}"]`)

        var new_amount = inventory_entry ? parseInt(inventory_entry.dataset.amount) + amount : amount

        if (inventory_entry) {
            // restore amount
            inventory_entry.dataset.amount = new_amount

            var counter = inventory_entry.querySelector("[data-name='count']")
            counter.innerText = new_amount
            inventory_entry.querySelector("input").max = new_amount
        } else {
            // recreate entry in inventory
            var new_inventory_entry = document.createElement("div")
            new_inventory_entry.classList.add("card")
            new_inventory_entry.dataset.id = id
            new_inventory_entry.dataset.type = type
            new_inventory_entry.dataset.name = name
            new_inventory_entry.dataset.image = image
            new_inventory_entry.dataset.details = details && details != 'None' && details != 'undefined' ? details : ''
            new_inventory_entry.dataset.can_recycle = parseInt(can_recycle)
            new_inventory_entry.dataset.amount = new_amount

            let recycle_msg = parseInt(can_recycle) ? "<p>Recyclable</p>" : ""

            var nametag = entry.querySelector('[data-mkt-role="name"]').outerHTML

            // this is the entry that goes back to the INVENTORY LIST
            new_inventory_entry.innerHTML = `
                <div class="medias" data-mkt-role="image">
                    <img class="mr-3" src="${image}">
                    <div class="media-body"></div>
                </div>

                <div class="item_list_content">
                    <div class="card-body-left">
                        <div class="item-number">
                            <div><p data-name="count">${new_amount}</p></div>
                        </div>
                        <div class="item-detail">
                            <div>${nametag}${recycle_msg}</div>
                        </div>
                    </div>
                    <div class="card-body-right">
                        <div class="item-input">
                            <span class="d-flex"><div><input type="number" class="form-control" value="0" max="${amount}" min="0" step="1"></div></span>
                        </div>
                        <div class="item-btn">
                            <button class="dashboard-btn" onclick="ts._add(this)"><span>Add</span></button>
                        </div>
                    </div>
                </div>`

            inventory.append(new_inventory_entry)
            _self.#_refresh_popovers()
        }

        entry.remove()
    }

    async #_refresh_popovers() {
        var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'))
        popoverTriggerList.forEach(popoverTriggerEl => new bootstrap.Popover(popoverTriggerEl) )
    }

    async #_update_their_local_bundle(action, element) {
        // update bundle to receive
        var _self = this

        if (action === "ADD") {
            let to_add = false

            var their_bundle = document.querySelector("#their_bundle")
            var entry = their_bundle.querySelector(`[data-id='${element.id}'][data-type='${element.type}']`)

            if (!entry) {
                var entry = document.createElement("div")
                entry.classList.add("card")
                entry.dataset.id = element.id
                entry.dataset.type = element.type
                to_add = true
            }

            // store details or empty string
            var details = element.details && element.details != 'None' && element.details != 'undefined' ? `
                data-bs-toggle="popover"
                data-bs-trigger="hover"
                data-bs-html="true"
                data-bs-placement="top"
                title="Unique traits"
                data-bs-content="${element.details}"
            ` : ''

            // this is the new entry of THEIR bundle
            var perks_mark = element.details && element.details != 'None' && element.details != 'undefined' ? ' <small class="mark bg-warning text-black">info</small>' : ''
            var recycle_msg = parseInt(element.can_recycle) ? '<p>Recyclable</p>' : ''

            entry.innerHTML = `
                <div class="medias" data-mkt-role="image">
                    <img class="mr-3" src="${element.image}">
                    <div class="media-body">
                    </div>
                </div>
                <div class="item_list_content">
                    <div class="card-body-left">
                        <div class="item-number">
                            <div>
                                <p data-name="count">${element.amount}</p>
                            </div>
                        </div>
                        <div class="item-detail">
                            <div>
                            <p data-mkt-role="name" ${details}>${element.name}${perks_mark}${recycle_msg}<p>
                            </div>
                        </div>
                    </div>
                </div>`

            if (to_add) {
                their_bundle.append(entry)
                _self.#_refresh_popovers()
            }

            _self.#_show_peer_locked(false)
            _self._reset_submit()
        } else if (action === "REMOVE") {
            var their_bundle = document.querySelector("#their_bundle")
            var entry = their_bundle.querySelector(`[data-id='${element.id}'][data-type='${element.type}']`)

            entry.remove()

            _self.#_show_peer_locked(false)
            _self._reset_submit()
        } else if (action == "BUNDLE_LOCKED") {
            _self.#_show_peer_locked(true)
        } else if (action == "UPDATE_BITS") {
            const their_bits = document.querySelector("#their_bits")
            their_bits.dataset.amount = element.amount
            their_bits.innerText = element.amount

            _self.#_show_peer_locked(false)
            _self._reset_submit()
        }
    }

    async #_show_peer_locked(show) {
        if (show) {
            document.querySelector("#peer_bundle_status").classList.remove("invisible")
        } else {
            document.querySelector("#peer_bundle_status").classList.add("invisible")
        }
    }

    async #_update_my_remote_bundle(action, data) {
        let response
        try {
            const headers = new Headers({ 'Content-Type': 'application/json', })
            const request = await fetch(location.pathname+'update/', {
              method: 'POST',
              headers: headers,
              cache: 'no-cache',
              credentials: 'same-origin',
              body: JSON.stringify({ action: action, data: data }),
            })

            response = await request.json()
            console.log("[DEBUG UPDATE RESPONSE]", response)
            if (response.error && response.error == 'OFFER_EXPIRED') {
                location.reload()
            }
        } catch (error) {
            console.log(error)
            response = {}
        }
        return response
    }
}
