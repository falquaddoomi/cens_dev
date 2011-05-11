$(document).ready(function() {
	// ====================================================================
	// === initialization (setting page scroll pos., structural stuff)
	// ====================================================================
	
	// ensure we start out at the top of the page...
	$.scrollTo(0);

	// wrap all of our header divs in a thickbox (just doing this for convenience)
	$("h1, h2").wrap("<div class='thickbox' />");

	// start out with all steps (and inner content) hidden, only progressing when the user's good and ready
	$(".step").hide().find(".content").hide();
	
	
	// ====================================================================
	// === navigation handlers
	// ====================================================================
	
	function moveToNextSection($me) {
		// show the href'd element
		// but first hide its inner content so we can slide it out
		var $target = $($me.attr("href"));

		if ($target.is(":hidden")) {
			// only do the animation if it wasn't visible in the first place
			$target.fadeIn(300, function() {
				$target.find(".content").slideDown(300, function() {
					$.scrollTo($target, { duration: 600, axis: 'y', offset: { left: 0, top: -10 } });
				});
			});
		}
		else {
			// just pan to the element
			$.scrollTo($target, { duration: 600, axis: 'y' });
		}
	}

	// associate a handler with each next link
	// we're going to fade in the next step, then pan down to it
	$(".nextbox a").not("a#link_to_step2, a#link_to_complete").click(function() {
		moveToNextSection($(this));
		return false;
	});
	
	// step 1 is special b/c it does validation before it continues
	$(".nextbox a#link_to_step2").click(function() {
		if ($('#signup_form').valid()) {
			moveToNextSection($(this));
		}
		else
		{
			$(".floater").fadeTo(0, 0, function() {
				$(this).fadeTo(400, 1);
			});
		}
		
		return false;
	});
	
	// step 3 is special as well
	$(".nextbox a#link_to_complete").click(function() {
		if (updateGoalMessageStatus()) {
			moveToNextSection($(this));
		}
		
		return false;
	});
	
	// and step 2 should at least do the validation...
	$("a#link_to_step3").click(function() {
		updateGoalMessageStatus();
	});

	// ====================================================================
	// === diagnosis checkbox list handlers
	// ====================================================================

	// for instance, make the "other, please describe" box show up only if that item is selected
	$("#diagnosis_other").change(function() {
		if ($(this).is(":checked")) {
			$("#diagnosis_other_info").fadeIn(300);
		}
		else {
			$("#diagnosis_other_info").fadeOut(100);
		}
	});
	// and make "don't know" gray the other options, since it excludes them
	$("#diagnosis_dont_know").change(function() {
		if ($(this).is(":checked")) {
			$("#diagnosis_list input:checkbox").not(this).attr('disabled', true);
		}
		else {
			$("#diagnosis_list input:checkbox").not(this).attr('disabled', false);
		}
	});
	
	
	// ====================================================================
	// === goal selectors and reorderable list
	// ====================================================================

	function updateGoalMessageStatus()
	{
		// update the status of the "no goals" message after every selection
		if ($(".goal_container input:radio").filter(":checked").not("[value='']").length > 0)
		{
			console.log("items: ",$(".goal_container input:radio").filter(":checked").not("[value='']").length);
			
			$("#no_goals_message").fadeOut(300);
			return true;
		}
		else
		{
			if ($("#no_goals_message").is(":visible")) {
				// flash the message
				$("#no_goals_message").fadeTo(0, 0, function() {
					$(this).fadeTo(400, 1);
				});
			}
			else
			{
				// show it for the first time
				$("#no_goals_message").fadeIn(300);
			}
			
			return false;
		}
	}
	
	function updateGoalsList()
	{
		var goals = [];
		
		$("#final_goals_list li").each(function() {
			goals.push($(this).attr("extra"));
		})
		
		// updates the hidden field that POSTs the goals to the server at the end
		$("#goals_list_hidden").val(goals.toString());
	}
	
	$("#no_goals_message").click(function() {
		$.scrollTo("#step2", { duration: 600, axis: 'y', offset: { left: 0, top: -10 } });
	});

	// bind up the controls that populate the reorderable list...
	$(".goal_container input:radio").change(function() {
		// find the label text that corresponds to this item
		var $label = $(this).next("label[for='" + $(this).attr("id") + "']");

		// make all other labels in this group non-selected and this one selected
		$(this).closest("ul").find("label").removeClass("selected").filter($label).addClass("selected");

		// remove the one with the corresponding class from our clathrin sheath (???)
		var $removingItem = $("#final_goals_list li." + $(this).attr("name"));

		if ($(this).val() == "") {
			// they selected the "no goal" goal, so just remove the item, even if it doesn't exist
			$removingItem.fadeOut().remove();
		}
		else if ($removingItem.length > 0) {
			// we actually have an item to remove, so remove it and insert the new one after
			// insert the new item after the current one, then remove the current one
			$("<li class='" + $(this).attr("name") + "'>" + $label.text() + "</li>")
				.hide()
				.insertAfter($removingItem)
				.fadeIn();

			$removingItem.fadeOut().remove();
		}
		else
		{
			// we have no item to remove, so simply append this new item
			$("<li class='" + $(this).attr("name") + "' value='" + $(this).attr("value") + "'>" + $label.text() + "</li>")
				.hide()
				.attr("extra", $(this).attr("extra"))
				.appendTo("#final_goals_list")
				.fadeIn();
		}
		
		updateGoalMessageStatus();
		updateGoalsList();
	});

	// finally, bind up that reorderable goals list!
	$("#final_goals_list").sortable({
		axis: 'y',
		opacity: 0.6,
		update: function(event, ui) {
			// ensure that the hidden element has the correct value
			updateGoalsList();
		}
	});
	$("#final_goals_list").disableSelection();
	
	// =================================
	// === deal with potential initial values on refresh
	// =================================
	
	// issue an initial change event to init the goal selector to previously populated values
	$(".goal_container input:radio").filter(":checked").change();
	
	// miscellanea
	
	$("#finished_button").hover(function() {
		$("#finish_callout").stop().animate({ right: "-=5px" }, 600);
	},
	function() {
		$("#finish_callout").stop().animate({ right: "+=5px" }, 600);
	});
});