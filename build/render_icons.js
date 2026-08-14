#!/usr/bin/osascript -l JavaScript
//
// assets/icons/*.svg 를 workflow/icons/*.png 로 굽는다.
//
// macOS 의 NSImage 가 SVG 를 네이티브로 읽으므로 별도 설치 없이 Apple 렌더러를
// 그대로 쓴다. 그라디언트·stroke-linecap·linejoin 이 모두 처리되고 안티에일리어싱
// 품질도 직접 구현한 래스터라이저보다 낫다.
//
// 한 번의 osascript 실행으로 전부 처리한다. 파일마다 프로세스를 띄우면 그것만으로
// 몇 초가 든다.
//
// 사용법: osascript -l JavaScript render_icons.js <svg 디렉터리> <png 디렉터리> <픽셀>

ObjC.import('AppKit');

function renderOne(srcPath, dstPath, pixels) {
  var image = $.NSImage.alloc.initWithContentsOfFile($(srcPath));
  if (!image || image.isNil()) {
    return 'SVG 를 읽지 못했습니다: ' + srcPath;
  }

  // 픽셀 수를 직접 지정한 비트맵에 그린다. NSImage.lockFocus 를 쓰면 화면의
  // 배율(레티나면 2배)에 따라 결과 크기가 달라져 기기마다 산출물이 갈린다.
  var rep = $.NSBitmapImageRep.alloc
    .initWithBitmapDataPlanesPixelsWidePixelsHighBitsPerSampleSamplesPerPixelHasAlphaIsPlanarColorSpaceNameBytesPerRowBitsPerPixel(
      $(), pixels, pixels, 8, 4, true, false, $.NSCalibratedRGBColorSpace, 0, 0);
  if (!rep || rep.isNil()) {
    return '비트맵을 만들지 못했습니다: ' + dstPath;
  }

  var context = $.NSGraphicsContext.graphicsContextWithBitmapImageRep(rep);
  $.NSGraphicsContext.saveGraphicsState;
  // 반드시 setCurrentContext 로 호출한다. currentContext = ... 속성 대입은 JXA 에서
  // 조용히 무시되고, 그러면 아무것도 그리지 않은 투명 PNG 가 성공으로 나온다.
  $.NSGraphicsContext.setCurrentContext(context);
  context.imageInterpolation = $.NSImageInterpolationHigh;
  context.shouldAntialias = true;

  image.drawInRectFromRectOperationFraction(
    $.NSMakeRect(0, 0, pixels, pixels),
    $.NSZeroRect,
    $.NSCompositingOperationSourceOver,
    1.0);

  $.NSGraphicsContext.restoreGraphicsState;

  // 빈 이미지가 조용히 통과하지 않도록 실제로 칠해졌는지 본다. 위의 대입 실수를
  // 이 검사가 없어서 한참 뒤에야 알아챘다.
  var painted = 0;
  for (var y = 0; y < pixels; y += 8) {
    for (var x = 0; x < pixels; x += 8) {
      if (rep.colorAtXY(x, y).alphaComponent > 0.05) { painted++; }
    }
  }
  if (painted < 8) {
    return '그려진 내용이 없습니다: ' + srcPath;
  }

  var png = rep.representationUsingTypeProperties($.NSBitmapImageFileTypePNG,
                                                  $.NSDictionary.dictionary);
  if (!png.writeToFileAtomically($(dstPath), true)) {
    return '저장하지 못했습니다: ' + dstPath;
  }
  return null;
}

function run(argv) {
  var srcDir = argv[0];
  var dstDir = argv[1];
  var pixels = parseInt(argv[2], 10);

  var manager = $.NSFileManager.defaultManager;
  manager.createDirectoryAtPathWithIntermediateDirectoriesAttributesError(
    $(dstDir), true, $(), null);

  var names = ObjC.deepUnwrap(manager.contentsOfDirectoryAtPathError($(srcDir), null)) || [];
  names = names.filter(function (name) { return /\.svg$/i.test(name); }).sort();

  // 이름이 바뀐 아이콘이 설치본에 남지 않도록 먼저 비운다.
  var stale = ObjC.deepUnwrap(manager.contentsOfDirectoryAtPathError($(dstDir), null)) || [];
  stale.forEach(function (name) {
    if (/\.png$/i.test(name)) {
      manager.removeItemAtPathError($(dstDir + '/' + name), null);
    }
  });

  var failures = [];
  names.forEach(function (name) {
    var base = name.replace(/\.svg$/i, '');
    var problem = renderOne(srcDir + '/' + name, dstDir + '/' + base + '.png', pixels);
    if (problem) { failures.push(problem); }
  });

  if (failures.length) {
    throw new Error(failures.join('\n'));
  }
  return names.length + '개 생성 (' + pixels + 'px)';
}
