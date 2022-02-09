$( document ).ready(function() {

    // Animate burger
    $('#nav-icon').click(function(){
		$(this).toggleClass('open');
        $('.header nav').toggleClass('active');
        $('.header').toggleClass('fixed');
	});

    // Sticky header
    let lastScrollTop = 0;
    $(window).scroll(function(event){
        let st = $(this).scrollTop();

        if (st > lastScrollTop) {
            $('.header').addClass('header-active');
            $('.header').removeClass('header-bg');
        } else {
            $('.header').removeClass('header-active');
            $('.header').addClass('header-bg');
        }
        lastScrollTop = st;
        if (lastScrollTop == 0) {
            $('.header').removeClass('header-active');
            $('.header').removeClass('header-bg');
        }
    });

    // // Smooth Scroll
    // $('.header-nav a').on('click', function(e) {
    //     e.preventDefault();
    //     if ($('#nav-icon').hasClass('open')) {
    //         $('#nav-icon').removeClass('open');
    //         $('.header nav').removeClass('active');
    //     } else {
    //         $('#nav-icon').removeClass('open');
    //         $('.header nav').removeClass('active');
    //     }

    //     let idListForLink = ['header-nav-team', 'header-nav-tutorial'];
    //     let link = $(this).attr('href');
    //     if(link != '/') {
    //         if (idListForLink.includes($(this).attr('id'))) {
    //             window.location.href = link;
    //         } else {
    //             let id = link.substring(1);
    //             if ($(id).length) {
    //                 $('html, body').animate({
    //                     scrollTop: $(id).offset().top
    //                 }, 500);
    //                 window.location.href = link;
    //             } else {
    //                 window.location.href = link;
    //             }
    //         }
            
    //     } else {
    //         window.location.href = '/';
    //     }
    // });

    // Show video on desctop 
    let windowWidth = jQuery('body').innerWidth();
    if($.browser.mobile){

    }
    else
    {
        if (jQuery('video').length  && windowWidth >= 767) {

            jQuery('video.hero-video').each(function() {
                let video = jQuery(this);
                let videoSource = video.find("source").attr('data-src');
                video.find("source").attr("src", videoSource);
                video.load();
                video[0].play();
            });
            
        }
    }
    
    // Hero section
    // Play video 
    $('.hero-section .play-video').on('click', function() {
        let video = $('.hero-video');
        video[0].play();
        $(this).hide();
        $('.hero-section .pause-video').show();
    });

    // Pause video
    $('.hero-section .pause-video').on('click', function() {
        let video = $('.hero-video');
        video[0].pause();
        $(this).hide();
        $('.hero-section .play-video').show();
    });

    // Video section
    // Play video 
    $('.video-section .play-video').on('click', function() {
        let video = $('.story-video');
        video[0].play();
        $(this).hide();
        $('.video-section .pause-video').show();
    });

    // Pause video
    $('.video-section .pause-video').on('click', function() {
        let video = $('.story-video');
        video[0].pause();
        $(this).hide();
        $('.video-section .play-video').show();
    });

    // FAQ accordion
    $('.faq-item-head').click(function() {
    
        if(!$(this).closest('.faq-item').hasClass('active')) {
                $('.faq-item').each(function() {
                $(this).removeClass('active');
            });
            $(this).closest('.faq-item').addClass('active');
        }
        else {
            $('.faq-item').each(function() {
                $(this).removeClass('active');
            });
    	}

    });

    // Custom select
    $('.shop-sorting').niceSelect();

    // Increment decrement button
    let priceInput = $(".number-input");

    priceInput.val(1);

    $(".number-btn ").click(function(){
        if ($(this).hasClass('inc'))
        priceInput.val(parseInt(priceInput.val())+1);
        else if (priceInput.val()>=1)
        priceInput.val(parseInt(priceInput.val())-1);
    });

    // Post archive accordion
    $('.archive-item-head ').click(function() {
    
        if(!$(this).closest('.archive-item').hasClass('active')) {
                $('.archive-item').each(function() {
                $(this).removeClass('active');
            });
            $(this).closest('.archive-item').addClass('active');
        }
        else {
            $('.archive-item').each(function() {
                $(this).removeClass('active');
            });
    	}

    });

    // Show active post
    $('.archive-item-body a').click(function(e) {
        e.preventDefault();

        $('.archive-item-body').each(function() {
            $(this).find('h4').removeClass('active');
        })

        $(this).closest('h4').addClass('active');
    })

    // Play / Stop tutorial video
    $('.tutorial .play-video').on('click', function() {
        let video = $(this).closest('.tutorial-slider-item').find('video');
        video[0].play();
        $(this).closest('.tutorial-slider-item').find('.video-controls').toggleClass('active');
        $(this).closest('.tutorial-slider-item').find('.tutorial-slider-content').addClass('hide');
    });
    $('.tutorial .pause-video').on('click', function() {
        let video = $(this).closest('.tutorial-slider-item').find('video');
        video[0].pause();
        $(this).closest('.tutorial-slider-item').find('.video-controls').toggleClass('active');
        $(this).closest('.tutorial-slider-item').find('.tutorial-slider-content').removeClass('hide');
    });

    // Pause all video
    $('.tutorial-slider-nav-item').on('click', function () {
       $('.tutorial-slider-item').each(function() {
            let video = $(this).find('video');
            video[0].pause();
       });
    });

    // Subscribe
    $('#news_letter_form').on('submit', function(event){
        event.preventDefault();
        $.ajax({
            url : "/subscription/", // the endpoint
            type : "POST", // http method
            headers: { "X-CSRFToken": getCookie("csrftoken") },
            data : { email : $('#subscribe_email').val() }, // data sent with the post request

            // handle a successful response
            success : function(json) {
                $('#subscribe_result').show();
                if (json.status == "success") {
                    $('#subscribe_result').addClass('alert-success');
                } else {
                    $('#subscribe_result').addClass('alert-warning');
                }
                $('#subscribe_result').html(json.result);
                $('#subscribe_email').val("");
                
                setTimeout(function(){
                    $('#subscribe_result').removeClass('alert-success alert-warning');
                    $('#subscribe_result').html("");
                    $('#subscribe_result').hide();
                }, 5000);
            },

            // handle a non-successful response
            error : function(xhr,errmsg,err) {
                $('#subscribe_result').show();
                $('#subscribe_result').addClass('alert-warning');
                $('#subscribe_result').html("Failed subscription");
                $('#subscribe_email').val("");
                console.log(xhr.status + ": " + xhr.responseText); // provide a bit more info about the error to the console
                setTimeout(function(){
                    $('#subscribe_result').removeClass('alert-success alert-warning');
                    $('#subscribe_result').html("");
                    $('#subscribe_result').hide();
                }, 5000);
            }
        });
    });

    const container = document.querySelector('#blog-posts-archive');
    if(container) {
        const ps = new PerfectScrollbar(container, {
            wheelSpeed: 2,
        });
    }

    function getCookie(c_name) {
        if (document.cookie.length > 0) {
            c_start = document.cookie.indexOf(c_name + "=");
            if (c_start != -1) {
                c_start = c_start + c_name.length + 1;
                c_end = document.cookie.indexOf(";", c_start);
                if (c_end == -1) {
                    c_end = document.cookie.length;
                }
                return unescape(document.cookie.substring(c_start,c_end));
            }
        }
        return "";
    }

});

// Blog posts archive custom scroll bar
// const container =
//     document.querySelector('#blog-posts-archive');
//     const ps = new PerfectScrollbar(container, {
//         wheelSpeed: 2,
//     });