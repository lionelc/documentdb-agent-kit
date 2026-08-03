// contoso-seed.js — Deterministic, RESUMABLE seeder for the Contoso
// "Dynamics 365 Sales" model on DocumentDB.
//
// Entities & relationships (faithful to the D365 Sales demo):
//   territories                (dimension)
//   users (salespeople)        -> territory_id
//   products                   (dimension; moderate text: description)
//   campaigns                  (BIG text: content)            scaled
//   accounts  -> territory_id, owner_id(user)  (BIG text: profile)   scaled
//   opportunities -> account_id, campaign_id, owner_id, territory_id  scaled
//        line_items:[ -> product_id ]
//        *** ANTI-PATTERN: big text (narrative + activity_log) co-located ***
//
// Large text is VARIED (low compressibility) so it lands in PostgreSQL TOAST.
//
// RESUMABLE: does not drop. For each collection it inserts only the missing
// documents (_id from have+1..target), so repeated runs converge to the target
// even if the container is killed mid-seed. Set CONTOSO_FRESH=1 to drop first.
//
// Env: CONTOSO_DB, CONTOSO_SCALE (1,2,4,6,8,16), CONTOSO_SEED (default 42),
//      CONTOSO_FRESH (1 to drop first).

var DB    = process.env.CONTOSO_DB || "contoso_x1";
var SCALE = parseInt(process.env.CONTOSO_SCALE || "1");
var SEEDV = parseInt(process.env.CONTOSO_SEED || "42");
var FRESH = process.env.CONTOSO_FRESH === "1";
var d = db.getSiblingDB(DB);

var _s = SEEDV >>> 0;
function rnd(){ _s|=0; _s=(_s+0x6D2B79F5)|0; var t=Math.imul(_s^(_s>>>15),1|_s); t=(t+Math.imul(t^(t>>>7),61|t))^t; return ((t^(t>>>14))>>>0)/4294967296; }
function ri(n){ return Math.floor(rnd()*n); }
function pick(a){ return a[ri(a.length)]; }

var CH="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789     .,;";
var POOL=""; while(POOL.length<24000) POOL+=CH[ri(CH.length)];
function text(n){ var o=ri(POOL.length-n-1); return POOL.substr(o,n); }

var N_TERR=12, N_USER=30, N_PROD=50*SCALE, N_CAMP=6*SCALE, N_ACCT=150*SCALE, N_OPP=500*SCALE;
var BATCH=100;

var INDUSTRIES=["Retail","Manufacturing","Finance","Healthcare","Technology","Energy","Education","Transport"];
var STAGES=["Qualify","Develop","Propose","Negotiate","Close"];
var STATES=["open","won","lost"];
var REGIONS=["NA-East","NA-West","EU-North","EU-South","APAC","LATAM"];
var CAMP_TYPES=["Email","Event","Webinar","Partner","Advertising"];

if (FRESH) ["territories","users","products","campaigns","accounts","opportunities"].forEach(function(c){ try{d[c].drop();}catch(e){} });

// Resumable insert: fill _id from have+1..target in batches.
function seedColl(name, target, make){
    var have = d[name].countDocuments();
    if (have >= target) return have;
    for (var start = have+1; start <= target; start += BATCH){
        var end = Math.min(start+BATCH-1, target);
        var b = [];
        for (var id = start; id <= end; id++) b.push(make(id));
        try { d[name].insertMany(b, {ordered:false}); } catch(e) { /* dup-key on resume overlap: ignore */ }
    }
    return d[name].countDocuments();
}

print("=== Seeding "+DB+" (scale x"+SCALE+") resumable ===");

seedColl("territories", N_TERR, function(id){ return {_id:id, territory_id:"TERR_"+id, name:"Territory "+id, region:REGIONS[id%REGIONS.length], manager:"Manager "+id}; });
seedColl("users", N_USER, function(id){ return {_id:id, user_id:"USR_"+id, full_name:"Rep "+id, title:pick(["AE","SAE","Manager"]), territory_id:(id%N_TERR)+1}; });
seedColl("products", N_PROD, function(id){ return {_id:id, product_id:"PROD_"+id, name:"Product "+id, category:pick(["Hardware","Software","Services","Support"]), list_price:100+ri(9900), unit_cost:50+ri(4000), description:text(400)}; });
seedColl("campaigns", N_CAMP, function(id){ return {_id:id, campaign_id:"CMP_"+id, name:"Campaign "+id, type:pick(CAMP_TYPES), budget:10000+ri(490000), start_date:new Date(2024,ri(12),1+ri(27)), expected_revenue:50000+ri(950000), content:text(4000)}; });
seedColl("accounts", N_ACCT, function(id){ return {_id:id, account_id:"ACC_"+id, name:"Account "+id, industry:pick(INDUSTRIES), city:"City"+ri(500), state:"ST"+ri(50), country:pick(["US","UK","DE","JP","BR"]), annual_revenue:100000+ri(50000000), num_employees:10+ri(9990), territory_id:(id%N_TERR)+1, owner_id:(id%N_USER)+1, profile:text(3500)}; });
seedColl("opportunities", N_OPP, function(id){
    var nItems=1+ri(4), items=[];
    for (var j=0;j<nItems;j++){ var qty=1+ri(20), ppu=100+ri(9900); items.push({product_id:(ri(N_PROD))+1, qty:qty, price_per_unit:ppu, amount:qty*ppu}); }
    var est=items.reduce(function(s,x){return s+x.amount;},0);
    var state=pick(STATES);
    return {_id:id, opportunity_id:"OPP_"+id, name:"Opportunity "+id, account_id:(ri(N_ACCT))+1, campaign_id:(ri(N_CAMP))+1, owner_id:(id%N_USER)+1, territory_id:(id%N_TERR)+1, est_value:est, actual_value:(state==="won"?est:0), probability:ri(101), sales_stage:pick(STAGES), state:state, created_at:new Date(2024,ri(12),1+ri(27)), est_close_date:new Date(2025,ri(12),1+ri(27)), line_items:items, narrative:text(3500), activity_log:text(2500)};
});

print("Counts: "+["territories","users","products","campaigns","accounts","opportunities"].map(function(c){return c+"="+d[c].countDocuments();}).join(" "));
print("DONE "+DB);
