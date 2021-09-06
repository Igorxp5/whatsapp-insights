class WhatsAppAPI {
	constructor() {
		this._lastTag = null;
        this._socketListeners = [];

        enableWebSocketIntercept(this._messageHandler, this._sendHandler);

		disconnectBrowserFromInternet();

	};

	getSocket = () => {
		return waitForCondition(function() {
			return window.sockets[window.sockets.length - 1] != undefined;
		}).then(function() {
			return window.sockets[window.sockets.length - 1];
		});
	}

    getContactProfileImage = (phoneNumber) => {
		let jid = this.getJid(phoneNumber);
		let request = ["query", "ProfilePicThumb", jid];
		return this._sendRequest(request, false).then((response) => {
			let data = JSON.parse(response); 
				data = (data && data.eurl) || null;
			return data;
		});
	}

    getJid = (phoneNumber) => {
		phoneNumber = phoneNumber.replace("@s.whatsapp.net", "");
		if (phoneNumber.endsWith("@c.us")) {
			return phoneNumber
		}
		return phoneNumber + "@c.us";
	}

    getLastTag = () => {
		return waitForCondition(() => {
			return this._lastTag != null;
		}).then(() => {
			return this._lastTag;
		});
	}

	getNextTag = () => {
		return this.getLastTag().then((tag) => {
			this._lastTag = {id: tag.id, inc: (parseInt(tag.inc) + 1).toString()};
			return this._lastTag;
		});
	}

    _getMessageInfo = (data) => {
        let content = null;
        if (typeof data == "string") {
            if (data.indexOf(",,") != -1) {
                content = data.slice(data.indexOf(",,") + 1);
            } else if (data.indexOf(",") != -1) {
                content = data.slice(data.indexOf(",") + 1);
            }
        }
        return {tag: this._getMessageTag(data), data: content};  
    }

    _getMessageTag = (data) => {
        if (typeof data == "string") {
            const regex = /^(\d{1,4})\.--(\d+)/gm;
            let match = regex.exec(data);
            if (match != null) {
                return {id: match[1], inc: match[2]};
            }
        }
        return null;
    }

    _sendRequest = (request, encrypt=false, timeout=80000) => {
		let requestTag;

		let requestPromise;
		if (typeof request == "object" && !encrypt) {
			let payload = JSON.stringify(request);
			requestPromise = this.getNextTag().then((tag) => {
				return this.getSocket().then((socket) => {
					let tagString = tag.id + '.--' + tag.inc;
					requestTag = tag;
					socket.send(tagString + ',,' + payload);
				});
			});
		}

		let resolveRequestPromise;
		let rejectRequestPromise;
		let timeoutToResponse;
		let requestSocketListener = (messageEvent) => {
            let responseTag = this._getMessageTag(messageEvent.data);
            let messageInfo = this._getMessageInfo(messageEvent.data);
            if (messageInfo.data && responseTag != null && responseTag.id == requestTag.id && responseTag.inc == requestTag.inc) {
                clearTimeout(timeoutToResponse);
                this._unregisterSocketListener(requestSocketListener);
                resolveRequestPromise(messageInfo.data);
            }
		}

		timeoutToResponse = setTimeout(() => {
			this._unregisterSocketListener(requestSocketListener);
			let err = new TimeoutError("server took long time to handle the request");
			console.error(err);
			rejectRequestPromise(err);
		}, timeout);

		return requestPromise.then(() => {
			return new Promise((resolve, reject) => {
				resolveRequestPromise = resolve;
				rejectRequestPromise = reject;
				this._registerSocketListener(requestSocketListener);
			});
		});
	}

    _messageHandler = (messageEvent) => {
		this._socketListeners.forEach(function(listener){
			setTimeout(function(){
				listener(messageEvent);
			}, 1); //call asynchronously
		});
	}

	_sendHandler = (data) => {
        let info = this._getMessageInfo(data);
		if (info.tag != null) {
			this._lastTag = {id: info.tag.id, inc: (parseInt(info.tag.inc) + 50).toString()};
		}
		return data;
	}

    _registerSocketListener = (callback) => {
		this._socketListeners.push(callback);
	}

	_unregisterSocketListener = (callback) => {
		const index = this._socketListeners.indexOf(callback);
		if (index > -1) {
			this._socketListeners.splice(index, 1);
		}
	}
};

function enableWebSocketIntercept(handleMessage, handleSend) {
	window.sockets = []; 
	window._WS = WebSocket;
	window._WS_send = WebSocket.prototype.send;

	WebSocket = function(url, protocols) {
		let s = new _WS(url, protocols);
		s.addEventListener("message", handleMessage);
		sockets.push(s);
		return s;
	}

	_WS.prototype.send = function(data) {
		let interceptedMessage = handleSend(data);
		if (interceptedMessage != null) {
			return window._WS_send.call(this, interceptedMessage);
		}
	}
}

function disconnectBrowserFromInternet() {
	let event = new Event('offline');
	window.dispatchEvent(event);
}

function waitForCondition(checkFunc, expectedValue=true, interval=500, timeout=120000) {

	let executor = function(resolve, reject) {
		var waitForConditionInterval = setInterval(function(){
			if (checkFunc() == expectedValue) {
				clearInterval(waitForConditionInterval);
				resolve();
			}
		}, interval);
		setTimeout(function() {
			clearInterval(waitForConditionInterval);
			reject("Timeout reached");
		}, timeout);
	}

	return new Promise(executor);
}

window.WhatsAppAPI = WhatsAppAPI;
