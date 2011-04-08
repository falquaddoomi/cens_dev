$(document).ready(function() {
	// a useful function for determining if something is in view...
	function isScrolledIntoView(elem, container)
	{
		if (container == null)
			container = window;
		
		// cache these since we use them frequently below
		var $container = $(container);
		var $elem = $(elem);
			
		var docViewTop = $container.scrollTop();
		var docViewBottom = docViewTop + $container.height();
		var docViewLeft = $container.scrollLeft();
		var docViewRight = docViewLeft + $container.width();
		
		var elemTop = $elem.offset().top;
		var elemBottom = elemTop + $elem.height();
		var elemLeft = $elem.offset().left;
		var elemRight = elemLeft + $elem.width();
		
		return	((docViewTop <= elemTop) && (docViewBottom >= elemBottom)) &&
				((docViewLeft <= elemLeft) && (docViewRight >= elemRight));
	}

	
	/*
	=========================================================================
	=== SLIDER STUFF
	=========================================================================
	*/
	
	var VISIBLE_PANELS = $("#visible_pages_select").val();
	
	$("#visible_pages_select").change(function() {
		var $select = $(this);
		
		$("#slider").fadeTo(200, 0, function() {
			VISIBLE_PANELS = $select.val();
			$(window).resize();
			$(this).fadeTo(200, 1);
		});	
	});
	
	// associate a handler to resize the panels when the window size changes
	// and closure these vars so we don't have to keep looking for them
	var $editor = $("#editor");
	var $slider = $editor.find("#slider"); // nab the slider
	var $panels = $slider.find(".panel"); // nab our panels
	
	$(window).resize(function() {
		// compute the size of the editor		
		var w = $editor.innerWidth();
		var h = $editor.innerHeight();

		// make them some multiple of the editor's width
		var computed_w = w/VISIBLE_PANELS;

		// make our panels the width and height of the editor view
		$panels.css({ "width": computed_w, "height": h });
		// make our tboxes tall enough
		$panels.find(".tbox").css("height", h-60);
		// make our slider the width of all the panels combined
		$slider.css("width", computed_w*$panels.length);
	});
	
	// and call it the first time
	$(window).resize();
	
	/*
	=========================================================================
	=== TEXTAREA EDITOR
	=========================================================================
	*/
	
	$(".tbox").each(function() {
		// collect a number of the usual characters
		var $toolbar = $(this).find(".toolbar");
		var $textarea = $(this).find("textarea");
		
		/* command registration */
		
		$toolbar.find("a[href='#lock']").click(function() {
			// do something fun for a change!
			$textarea.val(formatXml($textarea.val()));
		});
		
		$toolbar.find("a[href='#wrap']").click(function() {
			if ($(this).hasClass("wrap_cmd")) {
				$textarea.removeClass("nonwrapped").attr("wrap","");
				// and set the button to turn off wrapping now
				$(this).removeClass("wrap_cmd").addClass("nowrap_cmd").text("unwrap");
			}
			else {
				$textarea.addClass("nonwrapped").attr("wrap","off");
				$(this).removeClass("nowrap_cmd").addClass("wrap_cmd").text("wrap");
			}
		});
	});
	
	/*
	=========================================================================
	=== DOCUMENT CHOOSER
	=========================================================================
	*/
	
	$("#chooser .doc").click(function() {
		var $me = $(this);
		var $linked_panel = $("#slider .panel:eq(" + $(this).index() + ")");

		$("#chooser .doc").addClass("disabled").removeClass("selected").filter($me).addClass("selected");

		$("#editor").scrollTo($linked_panel, {
			axis: 'x',
			duration: 300,
			margin: true,
			onAfter: function() {
				// re-enable the selectors, perhaps?
				$("#chooser .doc").removeClass("disabled").removeClass("hidden");
				
				// determine which corresponding views are invisible and make their docs dimmed
				$("#slider .panel").each(function() {
					if (isScrolledIntoView(this, $(this).closest("#editor")))
						$me.addClass("hidden");
					else
						$me.removeClass("hidden");
				});
			}
		});
	});
	
	
	/*
	=========================================================================
	=== general page init stuff
	=========================================================================
	*/

	// set the tab size to 4 spaces for all textareas
	$("textarea").tabOverride();
	
	/*
	$("textarea").focus(function() {
		// activate the proper slider pane if the user is super clever
		var $linked_doc = $("#chooser .doc:eq(" + $(this).closest(".panel").index() + ")");
		
		if (!$linked_doc.hasClass("selected"))
			$linked_doc.click();
	});
	*/
	
	$(".command.notitle").hover(function() {
		$(this).stop().animate({ width: 70 }, 200);
	},
	function() {
		$(this).stop().animate({ width: 0 }, 200);
	});
});