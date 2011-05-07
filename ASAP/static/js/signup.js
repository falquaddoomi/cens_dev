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

	// associate a handler with each next link
	// we're going to fade in the next step, then pan down to it
	$(".nextbox a").click(function() {
		// show the href'd element
		// but first hide its inner content so we can slide it out
		var $target = $($(this).attr("href"));

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

		return false;
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
			$("<li class='" + $(this).attr("name") + "'>" + $label.text() + "</li>")
				.hide()
				.appendTo("#final_goals_list")
				.fadeIn();
		}
	});

	// finally, bind up that reorderable goals list!
	$("#final_goals_list").sortable({
		axis: 'y',
		opacity: 0.6
	});
	$("#final_goals_list").disableSelection();
});