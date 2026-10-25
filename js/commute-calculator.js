/* MetroGuideIndia – Namo Bharat RRTS Commute Calculator
 * Mount: <div id="mgi-commute-calculator" data-from="sarai-kale-khan" data-to="modipuram"></div>
 * Fares and parking tariffs are estimates; verify with NCRTC. */
(function () {
  'use strict';

  var STATIONS = [
    ['sarai-kale-khan', 'Sarai Kale Khan', 0],
    ['new-ashok-nagar', 'New Ashok Nagar', 4],
    ['anand-vihar', 'Anand Vihar', 8],
    ['sahibabad', 'Sahibabad', 17],
    ['ghaziabad', 'Ghaziabad', 20],
    ['guldhar', 'Guldhar', 28],
    ['duhai', 'Duhai', 32],
    ['murad-nagar', 'Murad Nagar', 40],
    ['modi-nagar-south', 'Modi Nagar South', 47],
    ['modi-nagar-north', 'Modi Nagar North', 51],
    ['meerut-south', 'Meerut South', 60],
    ['shatabdi-nagar', 'Shatabdi Nagar', 65],
    ['begumpul', 'Begumpul', 72],
    ['modipuram', 'Modipuram', 82]
  ];
  var DELHI = ['sarai-kale-khan', 'new-ashok-nagar', 'anand-vihar'];
  var FULL_FARE_KM = 82, FULL_FARE = 213, PREMIUM = 1.2, NCMC_DISC = 0.10;
  var PASS = { two: 600, four: 2000, cycle: 0 };

  // Per-duration daily parking (₹): [free, <=6h, 6-12h, 12-16h, full day]
  var TARIFF = {
    delhi: { two: [0, 10, 20, 30, 40], four: [0, 20, 40, 60, 80], cycle: [0, 2, 3, 4, 5] },
    up: { two: [0, 5, 10, 15, 20], four: [0, 15, 30, 45, 60], cycle: [0, 1, 2, 3, 4] }
  };
  var DURATIONS = [
    ['free', '<10m Pick/Drop (Free)', 0],
    ['6', 'Up to 6 hrs', 1],
    ['12', '6–12 hrs (Office Shift)', 2],
    ['16', '12–16 hrs', 3],
    ['full', 'Full Day', 4],
    ['monthly', 'Monthly Parking Pass', -1]
  ];
  var FREQS = [
    ['1', 'Single Trip', 0.5],
    ['2', '1 Day Round-Trip', 1],
    ['22', '22 Days/Month (5 days/wk)', 22],
    ['26', '26 Days/Month (6 days/wk)', 26]
  ];

  var root = document.getElementById('mgi-commute-calculator');
  if (!root) return;

  function idx(slug) {
    slug = (slug || '').toLowerCase().trim();
    for (var i = 0; i < STATIONS.length; i++) if (STATIONS[i][0] === slug) return i;
    return -1;
  }
  var from = idx(root.getAttribute('data-from'));
  var toAttr = (root.getAttribute('data-to') || '').trim();
  var to = idx(toAttr);
  if (from < 0) from = to >= 0 && to !== 0 ? 0 : 0;
  if (to < 0) to = from === idx('modipuram') ? idx('sarai-kale-khan') : idx('modipuram');
  if (to === from) to = from === STATIONS.length - 1 ? 0 : STATIONS.length - 1;

  var state = { from: from, to: to, coach: 'std', pay: 'single', park: 'none', dur: '12', freq: '22' };

  var css = '#mgi-commute-calculator{font-family:"DM Sans",system-ui,sans-serif;color:#1A1A1A;background:#fff;border:1px solid #EDE9E3;border-radius:16px;padding:18px;max-width:900px;margin:24px auto;box-sizing:border-box}' +
    '#mgi-commute-calculator *{box-sizing:border-box}' +
    '.mcc-title{font-family:"Syne",sans-serif;font-weight:700;font-size:1.2rem;color:#C0392B;margin:0 0 4px}' +
    '.mcc-sub{font-size:.8rem;color:#6b6b6b;margin:0 0 16px}' +
    '.mcc-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}' +
    '.mcc-ctl{background:#FDF0EC;border-radius:12px;padding:12px}' +
    '.mcc-ctl.wide{grid-column:1/-1}' +
    '.mcc-lbl{display:block;font-size:.7rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#6b6b6b;margin-bottom:8px}' +
    '.mcc-sel{width:100%;padding:10px;border:1px solid #EDE9E3;border-radius:10px;background:#fff;font:inherit;font-size:.9rem;color:#1A1A1A}' +
    '.mcc-row{display:grid;grid-template-columns:1fr 1fr;gap:10px}' +
    '.mcc-pills{display:flex;flex-wrap:wrap;gap:8px}' +
    '.mcc-pill{border:1px solid #EDE9E3;background:#fff;border-radius:999px;padding:8px 14px;font:inherit;font-size:.82rem;cursor:pointer;color:#1A1A1A}' +
    '.mcc-pill[aria-pressed=true]{background:#C0392B;border-color:#C0392B;color:#fff}' +
    '.mcc-badge{display:inline-block;margin-top:8px;background:#fff;border:1px solid #C84B31;color:#C84B31;border-radius:999px;padding:3px 10px;font-size:.72rem;font-weight:700}' +
    '.mcc-cards{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:18px}' +
    '.mcc-card{border:1px solid #EDE9E3;border-radius:12px;padding:14px;border-top:3px solid #C0392B}' +
    '.mcc-card h4{margin:0 0 6px;font-size:.72rem;text-transform:uppercase;letter-spacing:.08em;color:#6b6b6b}' +
    '.mcc-big{font-family:"Syne",sans-serif;font-size:1.6rem;font-weight:700;color:#C0392B;margin:2px 0 8px}' +
    '.mcc-line{display:flex;justify-content:space-between;gap:8px;font-size:.82rem;padding:2px 0}' +
    '.mcc-save{color:#1a7f37;font-weight:700}' +
    '.mcc-note{font-size:.72rem;color:#6b6b6b;margin-top:12px}' +
    '@media(max-width:640px){.mcc-grid,.mcc-cards{grid-template-columns:1fr}.mcc-row{grid-template-columns:1fr}.mcc-ctl.wide{grid-column:auto}}';
  var st = document.createElement('style');
  st.textContent = css;
  document.head.appendChild(st);

  function rs(n) { return '₹' + Math.round(n).toLocaleString('en-IN'); }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }

  function pills(name, opts, cur) {
    return '<div class="mcc-pills" role="group">' + opts.map(function (o) {
      return '<button type="button" class="mcc-pill" data-k="' + name + '" data-v="' + o[0] + '" aria-pressed="' + (cur === o[0]) + '">' + esc(o[1]) + '</button>';
    }).join('') + '</div>';
  }
  function select(name, opts, cur) {
    return '<select class="mcc-sel" data-k="' + name + '" aria-label="' + name + '">' + opts.map(function (o) {
      return '<option value="' + o[0] + '"' + (String(o[0]) === String(cur) ? ' selected' : '') + '>' + esc(o[1]) + '</option>';
    }).join('') + '</select>';
  }

  function fareFor(a, b, coach, pay) {
    var km = Math.abs(STATIONS[a][2] - STATIONS[b][2]);
    var f = Math.max(20, Math.round(km * FULL_FARE / FULL_FARE_KM));
    if (coach === 'prem') f = Math.round(f * PREMIUM);
    if (pay === 'ncmc') f = Math.round(f * (1 - NCMC_DISC));
    return { fare: f, km: km };
  }

  function compute() {
    var s = state, km = Math.abs(STATIONS[s.from][2] - STATIONS[s.to][2]);
    var region = DELHI.indexOf(STATIONS[s.from][0]) >= 0 ? 'delhi' : 'up';
    var one = fareFor(s.from, s.to, s.coach, s.pay).fare;
    var base = fareFor(s.from, s.to, s.coach, 'single').fare;
    var ncmcFare = fareFor(s.from, s.to, s.coach, 'ncmc').fare;
    var d = DURATIONS.filter(function (x) { return x[0] === s.dur; })[0];
    var parkDay = 0, parkMonthly = 0, parkLabel = 'No parking';
    if (s.park !== 'none') {
      var pass = PASS[s.park];
      if (d[2] === -1) { parkMonthly = pass; parkLabel = 'Monthly pass'; }
      else { parkDay = TARIFF[region][s.park][d[2]]; parkLabel = d[1]; }
    }
    var days = parseFloat(FREQS.filter(function (x) { return x[0] === s.freq; })[0][2]);
    var monthDays = days >= 22 ? days : 22;
    var monthlyPass = s.park === 'none' ? 0 : PASS[s.park];

    // Monthly: pay daily vs NCMC + monthly pass
    var dailyPlan = monthDays * (2 * base) + (parkMonthly ? parkMonthly : monthDays * parkDay);
    var smart = monthDays * 2 * ncmcFare + monthlyPass;
    var saved = Math.max(0, dailyPlan - smart);

    // Road vs train
    var roadKm = km * 1.15;
    var trainMin = Math.round(km / 70 * 60 + 10);
    var roadMin = Math.round(roadKm / 25 * 60);
    var bike = roadKm * 2.5, cab = 120 + roadKm * 15;
    return { region: region, one: one, km: km, parkDay: parkDay, parkMonthly: parkMonthly, parkLabel: parkLabel,
      days: days, monthDays: monthDays, dailyPlan: dailyPlan, smart: smart, saved: saved, trainMin: trainMin, roadMin: roadMin,
      bike: bike, cab: cab, trainTrip: one };
  }

  function line(a, b, cls) { return '<div class="mcc-line"><span>' + a + '</span><span' + (cls ? ' class="' + cls + '"' : '') + '>' + b + '</span></div>'; }

  function render() {
    var s = state, c = compute();
    var opts = STATIONS.map(function (x, i) { return [i, x[1]]; });
    var parkOpts = [['none', 'No Parking'], ['two', 'Two-Wheeler (Bike/Scooter)'], ['four', 'Four-Wheeler (Car)'], ['cycle', 'Bicycle']];
    var badge = s.park !== 'none' ? '<span class="mcc-badge">' + (c.region === 'delhi' ? 'Delhi' : 'UP') + ' NCRTC Parking Tariff Applied</span>' : '';

    var tripPark = c.parkMonthly ? 'Monthly pass' : rs(c.parkDay);
    var perVisit = c.parkMonthly ? 0 : c.parkDay;
    var oneTotal = c.one + perVisit;
    var rtTotal = 2 * c.one + perVisit;
    var tripsLabel = s.freq === '1' ? 'Single trip' : s.freq === '2' ? '1 day round-trip' : c.days + ' days/month';
    var cmp = c.saved > 0 ? line('Monthly rupees saved', rs(c.saved), 'mcc-save') : line('Monthly rupees saved', '₹0 (daily plan is already optimal)');

    root.innerHTML =
      '<h3 class="mcc-title">Commute Cost Calculator</h3>' +
      '<p class="mcc-sub">Namo Bharat RRTS fare, parking and monthly budget — updates live.</p>' +
      '<div class="mcc-grid">' +
      '<div class="mcc-ctl wide"><span class="mcc-lbl">1 · Origin &amp; Destination</span><div class="mcc-row">' +
      select('from', opts, s.from) + select('to', opts, s.to) + '</div></div>' +
      '<div class="mcc-ctl"><span class="mcc-lbl">2 · Coach Class</span>' +
      pills('coach', [['std', 'Standard Coach (1x)'], ['prem', 'Premium Coach (~1.2x)']], s.coach) + '</div>' +
      '<div class="mcc-ctl"><span class="mcc-lbl">3 · Payment / Pass Type</span>' +
      pills('pay', [['single', 'Single QR / Token'], ['ncmc', 'NCMC Card / RRTS Connect (10% off + points)']], s.pay) + '</div>' +
      '<div class="mcc-ctl wide"><span class="mcc-lbl">4 · Origin Station Parking</span>' +
      pills('park', parkOpts, s.park) + '<div>' + badge + '</div></div>' +
      '<div class="mcc-ctl wide"><span class="mcc-lbl">5 · Parking Duration &amp; Commute Frequency</span><div class="mcc-row">' +
      select('dur', DURATIONS, s.dur) + select('freq', FREQS, s.freq) + '</div></div>' +
      '</div>' +
      '<div class="mcc-cards" aria-live="polite">' +
      '<div class="mcc-card"><h4>One-Way Ticket + Parking</h4><div class="mcc-big">' + rs(oneTotal) + '</div>' +
      line(esc(STATIONS[s.from][1]) + ' → ' + esc(STATIONS[s.to][1]) + ' (' + c.km + ' km)', rs(c.one)) +
      line('Parking (' + esc(c.parkLabel) + ')', s.park === 'none' ? '₹0' : tripPark) + '</div>' +
      '<div class="mcc-card"><h4>Daily Round-Trip Total</h4><div class="mcc-big">' + rs(rtTotal) + '</div>' +
      line('Round-trip train fare', rs(2 * c.one)) +
      line('Daily parking fee', s.park === 'none' ? '₹0' : tripPark) +
      (s.pay === 'ncmc' ? line('Loyalty points', 'Earned on NCMC / app trips', 'mcc-save') : '') + '</div>' +
      '<div class="mcc-card"><h4>Monthly Commute Budget (' + c.monthDays + ' days)</h4><div class="mcc-big">' + rs(c.smart) + '</div>' +
      line('Pay daily (cash/QR + daily parking)', rs(c.dailyPlan)) +
      line('NCMC (10% off)' + (s.park === 'none' ? '' : ' + monthly pass'), rs(c.smart)) +
      (s.park === 'two' || s.park === 'four' ? line('Monthly parking pass', rs(PASS[s.park])) : '') + cmp + '</div>' +
      '<div class="mcc-card"><h4>Road vs Train Comparison</h4><div class="mcc-big">' + Math.max(0, c.roadMin - c.trainMin) + ' min saved</div>' +
      line('Train (one-way)', c.trainMin + ' min') +
      line('NH-58 / DME road traffic', c.roadMin + ' min') +
      line('Saved vs Two-Wheeler petrol (' + rs(c.bike) + ')', rs(Math.max(0, c.bike - c.trainTrip)), 'mcc-save') +
      line('Saved vs App Cab (' + rs(c.cab) + ')', rs(Math.max(0, c.cab - c.trainTrip)), 'mcc-save') + '</div>' +
      '</div>' +
      '<p class="mcc-note">Estimates based on distance-proportional RRTS fares (₹213 for the full corridor) and indicative NCRTC parking tariffs. Premium ≈ 1.2x. Verify at the station or the RRTS Connect app. Tickets for ' + esc(tripsLabel) + '.</p>';
  }

  root.addEventListener('click', function (e) {
    var b = e.target.closest && e.target.closest('.mcc-pill');
    if (!b) return;
    state[b.getAttribute('data-k')] = b.getAttribute('data-v');
    render();
  });
  root.addEventListener('change', function (e) {
    var k = e.target.getAttribute && e.target.getAttribute('data-k');
    if (!k) return;
    var v = e.target.value;
    if (k === 'from' || k === 'to') {
      state[k] = parseInt(v, 10);
      if (state.from === state.to) {
        var other = k === 'from' ? 'to' : 'from';
        state[other] = state[k] === STATIONS.length - 1 ? 0 : STATIONS.length - 1;
      }
    } else state[k] = v;
    render();
    var el = root.querySelector('[data-k="' + k + '"]');
    if (el && el.focus) el.focus();
  });

  render();
})();
