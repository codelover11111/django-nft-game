$(document).ready(function(){
    $('.navbar_toggler').click(function(){
        $('body').toggleClass('m_open');
    })

    $('.cart_link a').click(function(){
        $('.cart_notification').toggleClass('active');
    })
})

const date = new Date();
let year = date.getFullYear();
document.getElementById("allright-reserved").innerHTML = 'ALL RIGHTS RESERVED ' + year;

$(document).ready(function() {
	var s = $(".header_section");
	var pos = s.position();					   
	$(window).scroll(function() {
		var windowpos = $(window).scrollTop();
		if (windowpos >= pos.top & windowpos <=100) {
			s.removeClass("sticky");
		} else {
			s.addClass("sticky");	
		}
	});
});
