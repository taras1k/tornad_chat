
function process_data(data){
  console.log(data);
  if(data['status']=='message'){
    var chater = 'chater';
    if (data['user']){
      chater = data['user']
    };
    show_message(data['message'], chater)
  } else if(data['status']=='chat_ended'){
    chat_ended();
  } else if(data['status']=='chat_started'){
    chat_started();
  }
}

function clear(){
  $('#chat').empty();
}

function chat_ended(){
  clear();
  show_message('Closed.', 'info');
}

function chat_started(){
  clear();
  show_message('Connected.', 'info');
}

function show_message(message, status){
  var msg = $('<p />').text(message);
  if(status=='info'){
    msg.addClass('muted')
  } else if (status=='me'){00
    var label = $('<span />').addClass('label badge-success')
                             .text('me');
    msg.addClass('text-success');
    label.prependTo(msg);
  } else{
    var label = $('<span />').addClass('label badge-info')
                             .text(status);
    msg.addClass('text-info');
    label.prependTo(msg);
    $.titleAlert('new message');
  }
  msg.prependTo($('#chat'))
}

function open_websocket(url){

  var ws = new WebSocket(url);
  ws.onopen = function() {
    //show_message('Connected.', 'info');
  }
  ws.onmessage = function(event) {
    var data_msg = $.parseJSON(event.data);
    process_data(data_msg);
  }
  ws.onclose = function() {
    chat_ended();
  }
}
