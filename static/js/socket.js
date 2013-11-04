var tabActive;
var retries = 0;

window.onfocus = function () {
  tabActive = true;
};

window.onblur = function () {
    tabActive = false;
};

if (!(window.WebSocket)){
  window.location.replace('/not_supported');
};

function process_data(data){
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

function media_replacer(match, tag, data, close_tag, offset, string){
  var obj = $.parseJSON(data);
  console.log(obj);
  if (obj.mime=='text/html'){
    return  '<blockquote>'+
            '<p>'+
            obj.title+
            '<small>'+
            obj.content+
            ' <a href="'+obj.finalurl+'">'+
            obj.finalurl+
            '</a>'+
            '</small>'+
            '</p>'+
            '</blockquote>';

  }
  else if (obj.mime.split('/')[0]=='image'){
    return '<blockquote>'+
           '<img src="'+obj.finalurl+'"/>'+
           '</blockquote>';
  }
  else {
    return tag+data+close_tag;
  }
}

function show_message(message, status){
  var msg = $('<p />').addClass('lead').text(message);
  var pattern = /(\[media_content\])(.+)(\[\/media_content\])/g;
  msg.html(msg.html().replace(pattern, media_replacer))
  var hash_pattern = /(^|\s)#(\S+)($|\s)/g;
  msg.html(msg.html().replace(hash_pattern, " <a href='/room/$2'>#$2</a> "))
  if(status=='info'){
    msg.addClass('muted')
  } else if (status=='me'){00
    var label = $('<span />').addClass('label badge-success')
                             .addClass('lead')
                             .text('me');
    msg.addClass('text-success').addClass('text-right');
    label.appendTo(msg);
  } else{
    var label = $('<span />').addClass('label badge-info')
                             .addClass('lead')
                             .text(status);
    msg.addClass('text-info').addClass('text-left');
    label.prependTo(msg);
    if (!tabActive){
      $.titleAlert('new message');
    }
  }
  msg.prependTo($('#chat'))
}

var ws;

$('#logout').on('click', function(e){
  ws.close();
})

function open_websocket(url){

  ws = new WebSocket(url);

  ws.onopen = function() {
    retries = 0;
    //show_message('Connected.', 'info');
  }
  ws.onmessage = function(event) {
    var data_msg = $.parseJSON(event.data);
    process_data(data_msg);
  }
  ws.onclose = function() {
    if (retries<5){
        setTimeout(open_websocket, 1000, url);
    }
    retries++;
    //open_websocket(url);
  }
}
