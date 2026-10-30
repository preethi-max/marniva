(() => {
  let renderer, scene, camera, root, reticle, placedObject, mediaStream;
  let rotation = 0, scale = 1;
  let scenarioType = 'ship-flooding';
  let xrSession = null, hitSource = null, xrReticle = null;

  const status = message => { const el = document.getElementById('cameraStatus'); if (el) el.textContent = message; };
  const mode = message => { const el = document.getElementById('environmentMode'); if (el) el.textContent = message; };
  const material = (color, extra={}) => new THREE.MeshStandardMaterial({color, roughness: .48, metalness: .12, ...extra});

  function box(parent, size, position, color, name='') {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(...size), material(color));
    mesh.position.set(...position); mesh.name = name; parent.add(mesh); return mesh;
  }
  function sphere(parent, radius, position, color, name='') {
    const mesh = new THREE.Mesh(new THREE.SphereGeometry(radius, 12, 8), material(color, {transparent:true, opacity:.8}));
    mesh.position.set(...position); mesh.name = name; parent.add(mesh); return mesh;
  }
  function cylinder(parent, radiusTop, radiusBottom, height, position, color, name='') {
    const mesh = new THREE.Mesh(new THREE.CylinderGeometry(radiusTop, radiusBottom, height, 16), material(color));
    mesh.position.set(...position); mesh.name = name; parent.add(mesh); return mesh;
  }

  function makeShip() {
    const g = new THREE.Group();
    const hull = new THREE.Mesh(new THREE.BoxGeometry(3.6,.55,1.15), material(0x174f6d));
    hull.rotation.z=.025; hull.position.y=.25; g.add(hull);
    box(g,[3.0,.08,.95],[0,.58,0],0xdde7ea);
    box(g,[.62,.48,.58],[-1.02,.92,0],0xe8eceb);
    box(g,[.22,.2,.62],[-1.04,1.22,0],0xf0b844);
    [-1.15,-.75,.15,.55,1.15].forEach((x,i)=>box(g,[.48,.28,.5],[x,.92+(i%2)*.03,0],i%2?0xd8b24a:0x31576b));
    [0.9,-.5].forEach(x=>{ const chimney=cylinder(g,.09,.13,.5,[x,1.1,0],0xc8d4d8); chimney.rotation.z=.08; });
    return g;
  }

  function makeFlooding() {
    const g = makeShip();
    sphere(g,.16,[1.34,.22,.58],0xff3b30,'hazardMarker');
    const ring = new THREE.Mesh(new THREE.RingGeometry(.17,.23,24),new THREE.MeshBasicMaterial({color:0xff3b30,side:THREE.DoubleSide,transparent:true,opacity:.85})); ring.rotation.x=-Math.PI/2; ring.position.set(1.34,.61,.58); ring.name='warningRing'; g.add(ring);
    const water = box(g,[1.1,.035,.78],[.7,.59,0],0x25b9dc,'risingWater'); water.material.transparent=true; water.material.opacity=.72;
    return g;
  }

  function makeFire() {
    const g = new THREE.Group();
    box(g,[3.3,.12,2.1],[0,.02,0],0x263746);
    box(g,[.82,.82,.82],[-.85,.48,-.1],0x596a73,'engine'); cylinder(g,.18,.18,.75,[.82,.4,.05],0x3b4a54);
    box(g,[.58,.08,.58],[.82,.82,.05],0xaebdc4);
    for(let i=0;i<12;i++) {
      const flame=new THREE.Mesh(new THREE.ConeGeometry(.08,.28+Math.random()*0.18,7),new THREE.MeshBasicMaterial({color:i%2?0xffa51c:0xff3d00}));
      flame.position.set(-1.15+(i%5)*.12,.18+Math.floor(i/5)*.05,.55+(i%2)*.12); flame.name='flame'; g.add(flame);
      const smoke=sphere(g,.09,[-.95+(i%4)*.14,.65+(i%7)*.07,.5+(i%3)*.08],0x70808a,'smoke'); smoke.material.depthWrite=false;
    }
    return g;
  }

  function makeGas() {
    const g=new THREE.Group();
    box(g,[3,.07,1.7],[0,.03,0],0x344753);
    cylinder(g,.42,.42,1.05,[-.8,.55,0],0xe5a623,'gasCylinder'); cylinder(g,.12,.12,.7,[.15,.35,0],0x425762,'pipe');
    box(g,[.12,.12,.12],[.55,.35,0],0xffd23f,'valve');
    const ring=new THREE.Mesh(new THREE.RingGeometry(.55,.72,32),new THREE.MeshBasicMaterial({color:0xffcc33,side:THREE.DoubleSide,transparent:true,opacity:.4})); ring.rotation.x=-Math.PI/2; ring.position.set(.55,.06,0); ring.name='gasZone'; g.add(ring);
    for(let i=0;i<28;i++) { const p=sphere(g,.07,[.5+(Math.random()-.5)*1.0,.35+Math.random()*.9,(Math.random()-.5)*.8],0xffd344,'gasParticle'); p.userData.baseX=p.position.x; p.userData.phase=Math.random()*6; }
    return g;
  }

  function makeEvacuation() {
    const g=new THREE.Group();
    box(g,[3.8,.08,2.0],[0,.03,0],0x27627a);
    box(g,[.5,.18,1.25],[1.25,.18,.1],0xe8e9e7,'lifeboat');
    box(g,[.38,.28,.38],[-.95,.22,.55],0x2bb9a5,'muster');
    [-1.5,-.8,-.1,.6,1.3].forEach((x)=>box(g,[.5,.025,.12],[x,.1,-.65],0xf2d466,'routeMarker'));
    box(g,[.08,.5,.8],[-1.7,.28,.6],0xf04b50,'exit');
    return g;
  }

  function makePPE() {
    const g=new THREE.Group(); box(g,[3,.06,1.8],[0,.03,0],0x2f5264);
    const helmet=cylinder(g,.28,.22,.16,[-1,.35,0],0xffd23f,'helmet'); helmet.rotation.z=.08;
    sphere(g,.12,[-.55,.28,.3],0xffd23f,'glove'); sphere(g,.12,[-.55,.28,-.1],0xffd23f,'glove');
    box(g,[.5,.08,.7],[.05,.38,0],0xf04b40,'lifejacket');
    box(g,[.28,.12,.55],[.75,.18,.15],0x253746,'safetyBoot'); box(g,[.28,.12,.55],[1.08,.18,.15],0x253746,'safetyBoot');
    cylinder(g,.22,.22,.48,[1.45,.4,0],0x1c8e91,'breathingApparatus');
    return g;
  }

  function makeAlternativeFuel() {
    const g=new THREE.Group(); box(g,[3,.06,1.8],[0,.03,0],0x304b58);
    cylinder(g,.38,.38,.9,[-.7,.48,0],0x3f78b0,'fuelTank'); cylinder(g,.38,.38,.9,[.7,.48,0],0x3f78b0,'fuelTank');
    cylinder(g,.07,.07,1.9,[0,.38,0],0xffcf33,'fuelPipe'); const valve=sphere(g,.13,[0,.85,0],0xff3b30,'valve'); valve.scale.y=.5;
    for(let i=0;i<12;i++) sphere(g,.05,[0+(Math.random()-.5)*.25,.85+Math.random()*1.0,(Math.random()-.5)*.25],0xffcf33,'fuelVapor');
    return g;
  }

  function createScenario(type) {
    if(type==='ship-flooding'||type==='flooding') return makeFlooding();
    if(type==='engine-fire'||type==='engine-fire-safety') return makeFire();
    if(type==='gas-toxic'||type==='gas-leakage') return makeGas();
    if(type==='emergency-muster'||type==='emergency-evacuation') return makeEvacuation();
    if(type==='marine-ppe'||type==='ppe') return makePPE();
    if(type==='alternative-fuels') return makeAlternativeFuel();
    return makeFlooding();
  }

  function ensureRenderer(cameraActive=false) {
    if(renderer) return;
    const host=document.getElementById('trainingScene');
    const canvas=document.createElement('canvas'); canvas.id='arCanvas'; canvas.className='ar-webxr-canvas'; host.appendChild(canvas);
    renderer=new THREE.WebGLRenderer({canvas,alpha:true,antialias:true}); renderer.setPixelRatio(Math.min(window.devicePixelRatio,2)); renderer.setClearColor(0x061829,.38);
    scene=new THREE.Scene(); camera=new THREE.PerspectiveCamera(48,1,.1,100); camera.position.set(0,1.4,4.2); camera.lookAt(0,.45,0);
    scene.add(new THREE.HemisphereLight(0xeefaff,0x173340,2)); const key=new THREE.DirectionalLight(0xffffff,2); key.position.set(3,5,4); scene.add(key);
    root=new THREE.Group(); scene.add(root);
    xrReticle=new THREE.Mesh(new THREE.RingGeometry(.09,.11,32),new THREE.MeshBasicMaterial({color:0x35d6c7,side:THREE.DoubleSide,transparent:true,opacity:.9})); xrReticle.rotation.x=-Math.PI/2; xrReticle.visible=false; xrReticle.matrixAutoUpdate=false; scene.add(xrReticle);
    resize(); window.addEventListener('resize',resize);
    renderer.setAnimationLoop(animate);
  }

  function resize() { const host=document.getElementById('trainingScene'); if(!host||!renderer) return; const w=host.clientWidth,h=host.clientHeight; renderer.setSize(w,h,false); camera.aspect=w/h; camera.updateProjectionMatrix(); }
  function animate(time, frame) { if(!renderer) return; resize(); if(root){ root.rotation.y=rotation; root.scale.setScalar(scale); }
    if(frame&&hitSource){ const hits=frame.getHitTestResults(hitSource); if(hits.length){ xrReticle.visible=true; xrReticle.matrix.fromArray(hits[0].getPose(renderer.xr.getReferenceSpace()).transform.matrix); } else xrReticle.visible=false; }
    scene.traverse(o=>{
      if(o.name==='risingWater') { o.position.y=.59+(Math.sin(time*.002)+1)*.025; o.scale.y=.9+Math.sin(time*.003)*.12; }
      if(o.name==='flame') o.scale.y=.8+Math.sin(time*.012+o.position.x)*.28;
      if(o.name==='smoke') {o.position.y+=.0018; if(o.position.y>1.4)o.position.y=.65;}
      if(o.name==='gasParticle'||o.name==='fuelVapor') {o.position.y+=.0015; o.position.x+=Math.sin(time*.002+o.userData.phase)*.0008; if(o.position.y>1.45)o.position.y=.35;}
      if(o.name==='warningRing'||o.name==='gasZone') o.scale.setScalar(1+Math.sin(time*.005)*.12);
    }); renderer.render(scene,camera); }

  function resetScene(type=scenarioType) { if(!renderer)return; scenarioType=type||scenarioType; rotation=0; scale=1; while(root.children.length)root.remove(root.children[0]); const obj=createScenario(scenarioType); obj.rotation.y=0; root.add(obj); placedObject=obj; mode('Prototype camera AR · 3D object visible'); status('3D hazard rendered. Tap a position or use controls to inspect it.'); }
  async function startCamera() {
    const video=document.getElementById('cameraPreview'); status('Requesting camera permission…');
    if(!navigator.mediaDevices?.getUserMedia){ status('Camera is unavailable in this browser. Use the WebGL 3D preview.'); ensureRenderer(false); resetScene(); return false; }
    if(!window.isSecureContext && location.hostname!=='localhost' && location.hostname!=='127.0.0.1'){status('Camera access requires HTTPS or localhost.'); ensureRenderer(false); resetScene(); return false;}
    try{ mediaStream=await navigator.mediaDevices.getUserMedia({video:{facingMode:{ideal:'environment'},width:{ideal:1280}},audio:false}); video.srcObject=mediaStream; video.hidden=false; await video.play(); ensureRenderer(true); resetScene(scenarioType); status('Camera active · prototype placement enabled. Tap the camera area to position or reposition the object.'); mode('Camera + 3D prototype AR'); hostPlaceHandler(); return true; }
    catch(error){ ensureRenderer(false); resetScene(); status(error.name==='NotAllowedError'?'Camera permission denied. Allow camera access, or use 3D preview.':'Camera unavailable ('+error.name+'). 3D preview remains active.'); mode('3D preview fallback'); return false; }
  }
  function hostPlaceHandler(){ const host=document.getElementById('trainingScene'); host.onclick=event=>{ if(!root||!placedObject)return; const r=host.getBoundingClientRect(); const x=(event.clientX-r.left)/r.width-.5; placedObject.position.x=THREE.MathUtils.clamp(x*2.8,-2.8,2.8); placedObject.position.y=event.clientY-r.top>r.height*.65?-.05:.05; status('Prototype object positioned in camera view.'); }; }

  async function startWebXR(){
    if(!navigator.xr){ status('True WebXR is unavailable here. Starting camera + touch-placement 3D prototype.'); await startCamera(); return; }
    try{ if(!await navigator.xr.isSessionSupported('immersive-ar')){status('Immersive WebXR is unavailable. Starting camera + touch-placement prototype.');await startCamera();return;} ensureRenderer(true);
      xrSession=await navigator.xr.requestSession('immersive-ar',{requiredFeatures:['hit-test']}); renderer.xr.enabled=true; await renderer.xr.setSession(xrSession); xrSession.addEventListener('select',()=>{if(xrReticle?.visible){root.position.setFromMatrixPosition(xrReticle.matrix);status('3D hazard anchored to the detected surface.');}});
      const viewer=await xrSession.requestReferenceSpace('viewer'); hitSource=await xrSession.requestHitTestSource({space:viewer}); resetScene(); mode('Live WebXR tracked AR'); status('Move the device to detect a surface. Tap to place the 3D object.');
    }catch(error){status('WebXR could not start. Starting camera + touch-placement prototype.');await startCamera();}
  }

  function stopCamera(){ if(mediaStream){mediaStream.getTracks().forEach(t=>t.stop());mediaStream=null;} const video=document.getElementById('cameraPreview'); video.srcObject=null; video.hidden=true; }
  function exposureScenario(type){ scenarioType=type||document.getElementById('moduleSelect')?.value||scenarioType; resetScene(scenarioType); }
  function rotate(delta=Math.PI/8){rotation+=delta;if(placedObject)placedObject.rotation.y=rotation;}
  function zoom(delta=.15){scale=THREE.MathUtils.clamp(scale+delta,.45,2.5);}
  document.addEventListener('DOMContentLoaded',()=>{
    ensureRenderer(false); exposeScene();
    document.getElementById('cameraBtn')?.addEventListener('click',startCamera);
    document.getElementById('arBtn')?.addEventListener('click',startWebXR);
    document.getElementById('arRotateBtn')?.addEventListener('click',()=>rotate());
    document.getElementById('arScaleBtn')?.addEventListener('click',()=>zoom(.15));
    document.getElementById('arScaleDownBtn')?.addEventListener('click',()=>zoom(-.15));
    document.getElementById('arResetBtn')?.addEventListener('click',()=>resetScene());
    document.getElementById('moduleSelect')?.addEventListener('change',event=>exposureScenario(event.target.value));
  });
  function exposeScene(){const host=document.getElementById('trainingScene');host.classList.add('camera-ar-ready');resetScene(scenarioType);}
  window.ARTraining={startCamera,startWebXR,stopCamera,resetScene,rotate,zoom,setScenario:exposureScenario};
  window.startWebXRTraining=startWebXR;
})();
