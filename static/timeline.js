$(function () {
  $('#flags-container').collapse('show')
  // composes an empty graph with no query
  if (query === null) {
    composeGraph('Click a flag', medalSeries(dates.length))
  } else {
    prepareGraph(query)
  }

  $('.countries').click(function(e) {
    prepareGraph(e.currentTarget.id)
  });
});

function prepareGraph(country) {
  // when another country is selected, clear the info section
  $( '#medals-info').html('Medals from a selected date will be shown here')
  $( '#date-header').html('Click on a column to see details')

  var series = medalSeries(dates.length);
  rows[country].forEach(function (medal) {
    // places 1, 2, 3 have indices 0, 1, 2
    var place = medal.place - 1
    // medals are placed in data array based on date index to preserve timeline
    var date = dates.indexOf(medal.date)
    ++series[place].data[date];
  })
  composeGraph(country, series)
};


// each medal is an object in array, containing name, rgb-color
// and an array, where each entry indicates the amount of won medals
function medalSeries(days) {
  var timelines = new Array(3);
  [['Gold', '#ffff00'],
  ['Silver', '#c0c0c0'],
  ['Bronze', '#cc9900']].forEach(function (metal, index) {
    //add zeroes as default values of won medals
    timelines[index] = ({
      name: metal[0],
      color: metal[1],
      data: new Array(days).fill(0)
    })
  })
  return timelines
};

var medalsTemplate = $('#medals-template').html();

// fill mustache template and run opening animation
function showDayTable(country, date) {
  $('#date-header').html(date)

  var dateMedals = rows[country].filter(medal => medal.date === date)

  var shown = $('.multi-collapse.collapse.show')
  // if medals table is open - close and reopen
  // if countries - close it and open medals simultaneously
  let card_event = shown.prop('id') === 'medals-container' ?
    'hidden.bs.collapse' : 'hide.bs.collapse'
  shown.one(card_event, function () {
    $('#medals-info').html(Mustache.render(medalsTemplate, dateMedals))
    $('#medals-container').collapse('show')
  })
  shown.collapse('hide')
};

function composeGraph(country, series) {

  var myChart = Highcharts.chart('container', {
    chart: {
      type: 'column',
    },
    title: {
      text: country
    },
    xAxis: {
      categories: dates,
    },
    yAxis: {
      min: 0,
      title: {
        text: 'Medals'
      },
      tickInterval: 1,
      stackLabels: {
        enabled: true,
        style: {
          fontWeight: 'bold',
          color: (Highcharts.theme && Highcharts.theme.textColor) || 'gray'
        }
      }
    },
    legend: {
      align: 'right',
      x: -30,
      verticalAlign: 'top',
      y: 25,
      floating: true,
      backgroundColor: (Highcharts.theme && Highcharts.theme.background2) || 'white',
      borderColor: '#CCC',
      borderWidth: 1,
      shadow: false,
      labelFormatter: function() {
        var total = 0;
        Highcharts.each(this.userOptions.data, function(value) {
          total += value;
        });
        return this.name + ': ' + total;
      }
    },
    tooltip: {
      headerFormat: '<b>{point.x}</b><br/>',
      pointFormat: '{series.name}: {point.y}<br/>Total: {point.stackTotal}'
    },
    plotOptions: {
      column: {
        stacking: 'normal',
      },
      series: {
        cursor: 'pointer',
        events: {
          click: function (event) {
            showDayTable(country, event.point.category)
          }
        }
      }
    },
    series: series
  })
}
