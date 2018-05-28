var thread_id;

// Exposed function to Python
eel.expose(js_random);
function js_random() {
    return Math.random();
}

eel.expose(set_thread)
function set_thread(int){
	thread_id = int;
	console.log('thread_id = '+int);
}

eel.expose(js_pre)
function js_pre(str) {
	$('#output').prepend(str+'</br>');
	$('#output').scrollTop = $('#output').scrollHeight;
}

eel.expose(poll)
function poll(thread_id) {
    poller = setInterval(get_poll, 2000, thread_id);
};

//#################################################################

function get_poll(thread_id) {
    data = eel.update_monitor(thread_id)(js_status);
};

// Local functions
function load_setup(){
	$("#setup").load( "form.html" );
}

function js_status(data) {
	if (data.exitFlag) {
	    $('#setup').collapse("show");
	    $('#status').collapse("hide");
	    $('#progress').collapse("hide");
	    $('#stop_form').collapse("hide");
	    $('#console_form').collapse("hide");
	    $('#console').collapse("hide");
	    clearInterval(poller);
	} else {
		//$('#output').html(JSON.stringify(data, undefined, 2));
		$('#msg').html(data.msg1+"<br>"+data.msg2);
		$('#md5').html(data.md5);
		$('#sha1').html(data.sha1);
		$('#album_title').html(data.album);
		$('#fname').html(data.filename);
		$('#pba_text').html('Album: '+data.actual_album+' of '+data.total_albums);
		$('#pbp_text').html('Photo: '+data.actual_image+' of '+data.total_images);
		$('#pb_albums').css('width', data.pb_albums+'%').attr('aria-valuenow', data.pb_albums).html('<span>'+data.actual_album+' of '+data.total_albums+'</span>');
		$('#pb_photos').css('width', data.pb_photos+'%').attr('aria-valuenow', data.pb_photos).html('<span>'+data.actual_image+' of '+data.total_images+'</span>');
		$('#pb_upload').css('width', data.upload_progress+'%').attr('aria-valuenow', data.upload_progress).html('<span>'+data.upload_progress+'%'+'</span>');
	};
}

function get_user_list() {
	data = eel.get_user(username="")(pop_list);
}

function pop_list(data) {
	$('#username').empty();
  $('#username').append($('<option></option>').val('').html('- Please make a selection -'));
	$.each(data, function(i,p) {
		$('#username').append($('<option></option>').val(p).html(p));
	});	
}

function get_user_config(username) {
	data = eel.get_user(username)(pop_form);
}

function pop_form(data) {
	$('#main_dir').val(data.main_dir);
	$('#main_dir').prop('disabled', true);
	//Populate subdir dropdown
	dirs = data.dirs;
	$('#subdir').empty();

	$('#subdir').append($('<option></option>').val('').html('Main upload directory (including all subdirectories)'));
	$.each(dirs, function(i,p) {
		$('#subdir').append($('<option></option>').val(p).html(p));
	});
}

function getFormObj(formId) {
    var formObj = {};
	formObj["username"] = $("#username").val();
	formObj["main_dir"] = $("#main_dir").val();
	formObj["subdir"] = $("#subdir").val();
	formObj["action"] = $("#action").val();
	formObj["update"] = $("#update").is(":checked");
	formObj["public"] = $("#public").is(":checked");
	formObj["friends"] = $("#friends").is(":checked");
	formObj["family"] = $("#family").is(":checked");
    return formObj;
}

//#################################################################
$("#username").on("change", function() {
	var username = $("#username").val();
	get_user_config(username);
});

$( "#setup_form" ).submit(function( event ) {
	event.preventDefault();
	data = getFormObj('setup_form');

	$('#setup').collapse("hide");
    $('#status').collapse("show");
    $('#progress').collapse("show");
    $('#stop_form').collapse("show");
    $('#console_form').collapse("show");
    eel.proc_iput(data);
});

$( "#stop_form" ).submit(function( event ) {
	event.preventDefault();
    //Stop current thread//
	eel.stop_thread(thread_id);
	console.log('stopping thread');
});

$( "#console_form" ).submit(function( event ) {
	event.preventDefault();
	$('#console').collapse("toggle");
});

/*
$('#submit').click(function() {
	data = getFormObj('setup_form');
	$('#output').html(JSON.stringify(data, undefined, 2));
    $('#setup').collapse("hide");
    $('#status').collapse("show");
    $('#progress').collapse("show");
    //eel.py_loop();
});
*/
