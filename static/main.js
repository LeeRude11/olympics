$( document ).ready(function() {
  composeTable();
  $('.sports').click(function() {
    composeTable($(this).prop('id'))
  });
  // Expand and Collapse buttons to control all cards
  $('.control-btns button').click(function() {
    $('.collapse').collapse($(this).val())
  })
});


function composeTable(sport) {
  var view = []
  // currying so that the rest of the function is same
  var iterateMedals = sport ? filterMedals.bind(null, sport) : allMedals
  for (country in rows) {
    var current = new CountryObject(country);
    iterateMedals(rows[country], current, view)
  }
  view.sort(compareScore);
  $('#countries-table').html(Mustache.render($('#table-template').html(), view));
}

function allMedals(country, current, view) {
  country.forEach(function (medal) { addMedal(medal, current) })
  view.push(current)
}

function filterMedals(sport, country, current, view) {
  country.filter(medal => medal['sport'] === sport).forEach(function (medal) {
    addMedal(medal, current)
  })
  if (current.medals.length)
    view.push(current)
}

// increment the amount of country's placings
function addMedal(medal, current) {
  current.medals.push(medal)
  var value = 'place' + [medal['place']]
  current[value]++
}


function compareScore(a, b) {
  return (b.place1 - a.place1) * 100 + (b.place2 - a.place2) * 10 + (b.place3 - a.place3)
}

function CountryObject(country) {
  this.country = country,
  this.medals = [],
  this.place1 = 0,
  this.place2 = 0,
  this.place3 = 0
}
