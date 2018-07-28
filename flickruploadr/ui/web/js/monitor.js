eel.expose(poll)
function poll(thread_id) {
	//setTimeout(get_poll, 100, thread_id);
    setInterval(get_poll, 100, thread_id);
};

function get_poll(thread_id) {
    data = eel.update_monitor(thread_id)(js_status);
};