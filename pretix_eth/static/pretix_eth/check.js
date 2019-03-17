$(document).ready(function(){var myVar; myVar = setInterval(check, 60000); }); 
function check(){
	location.reload();
	//alert('aaaaa');
	/*
  $.get("https://api.ethplorer.io/getAddressTransactions/0xb297cacf0f91c86dd9d2fb47c6d12783121ab780?apiKey=freekey", 
        function(data, status){ 
          if(data[0]['success'] === true && data[0]['value'] == 0.2296302161691345  && data[0]['to'] == 0xb9D13879DDb2dCB03ebA3ebcbddBAF065A42b3CE)
          {
            window.location.replace(); 
          }else {
            alert("Data: " + data[0]['value'] + "\nStatus: " + status); 
          }
        }
       ); */
}


