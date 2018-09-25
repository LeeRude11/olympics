var SCORING = {'1': 100, '2': 10, '3': 1}

$(function () {
  // if some values remained, load them
  getAthletes();
  getEvents();

  // loading events first prevents passing wrong events to getAthletes()
  $('#sport').change(getEvents)
  $('#parameters-container').change(getAthletes)

  $('th').click(sortRows)
});

// (modified) sorting by Nick Grealy:
// https://stackoverflow.com/a/19947532/9728623
function sortRows(e) {

  var table = $(this).parents('table').eq(0)
  var visible_tb = table.find('tbody').filter(':visible')
  var rows = table.find('tr:gt(0)').toArray().sort(comparer($(this).index()))


  // reverse only if sorting_asc was clicked so function is event handler
  $(this).prop( 'class', function( i, val ) {
    if (typeof(e) !== 'undefined' && val == 'sorting_asc') {
      rows = rows.reverse()
      return 'sorting_desc'
    }
    return 'sorting_asc'
  });

  $(this).siblings().prop('class', 'sorting')

  for (let i = 0; i < rows.length; i++){visible_tb.append(rows[i])}
}

function comparer(index) {
  return function(a, b) {
    var valA = getCellValue(a, index), valB = getCellValue(b, index)
    if ($.isNumeric(valA) && $.isNumeric(valB)) {
      return valA - valB
    }
    // empty strings are sorted below others
    // when string is empty use the other string but extended instead
    // so that non-empty one is placed above the other
    else {
      return (valA || (valB + 1)).toString().localeCompare(valB || (valA + 1))
    }
  }
};

var getCellValue = {
  results: function(row, index) {
    var sought_cell = $(row).children('td').eq(index)
    return sought_cell.text() || sought_cell.find('img').prop('title')
  },
  athletes: function(row, index) {
    var sought_cell = $(row).children('td').eq(index)
    // score <td> has text and class, name has text and sport has only img
    return sought_cell.prop('class') || sought_cell.text() || sought_cell.find('img').prop('title')
  }
}[page_name]

// one field is checked before AJAX request
var requiredField = {
  results: 'an_event',
  athletes: 'country'
}[page_name]

var initial_sort = {
  results: 0,
  athletes: 2
}[page_name]

var app_route = '/list_' + page_name

function getAthletes() {

  let parameters = {}
  $('#parameters-container > div').each(function(){
    field = $(this).find('select, input')
    parameters[field.prop('id')] = field.prop('checked') === undefined ?
      field.val() : field.prop('checked')
  })
  disabledStatus();

  if (parameters[requiredField] == '') {
    $('tbody.switch').html('')
    $('span.switch').html('0')
    return null
  }

  $.getJSON(app_route, parameters, function(data) {
    toggleDisplay(data);
  })
};

function getEvents() {
  // remove all but placeholder
  $('#an_event option:not(:first-child)').remove();
  let sport = $('#sport').val()
  if (sport !== '')
    fillTemplate('#events', $('#an_event'), sports_events[sport]);
};

// disable dropdown menus, whose previous siblings don't have a value
function disabledStatus() {
  $('#country, #sport').each(function(i, menu) {
    // disable next if current is undefined or disabled
    $('select').eq(i+1).prop('disabled', function() {
      return !$(menu).val() || $(menu).prop('disabled') ? true : false
    });
  })
};

// alternate table (and span) for a smoother transition
function toggleDisplay(data) {
  var show = $('.switch').filter(':hidden')

  var length = 0
  if (page_name === 'results' && data[0].athletes.length > 1) {
    data.forEach(function(team) {
      length += team.athletes.length
    })
  } else {
    length = data.length
  }
  show.filter('span').html(length)
  fillTemplate('#' + page_name, show.filter('tbody'), data)
  $('.switch').filter(':visible').toggle(0, function() {
    $(this).empty()
  })
  show.toggle(200, 'linear')
  // run sorting by rank on load
  sortRows.call($('th').eq(initial_sort))
}

// use mustache template for either athletes list or events list
function fillTemplate(tmpl_id, jq_object, data) {
  var template = $(tmpl_id + '-template').html()
  jq_object.append(Mustache.render(template, data))
}
