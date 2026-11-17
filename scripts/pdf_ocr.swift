// OCR local de uma página; o documento e a senha não são enviados a serviços externos.
import Foundation
import PDFKit
import Vision
import AppKit

func fail(_ message: String) -> Never {
    FileHandle.standardError.write(Data(message.utf8)); exit(1)
}
guard CommandLine.arguments.count >= 3 else { fail("Informe PDF e página.") }
let path = CommandLine.arguments[1]
guard let document = PDFDocument(url: URL(fileURLWithPath:path)) else { fail("PDF inválido.") }
if document.isLocked {
    let password = String(data:FileHandle.standardInput.readDataToEndOfFile(),encoding:.utf8) ?? ""
    guard document.unlock(withPassword:password) else { fail("Senha inválida.") }
}
guard let number = Int(CommandLine.arguments[2]), let page = document.page(at:number-1) else { fail("Página inválida.") }
let rect=page.bounds(for:.mediaBox)
guard rect.width>0, rect.height>0, rect.width<5000, rect.height<5000 else { fail("Dimensões inválidas.") }
let scale=min(2.5,3000/max(rect.width,rect.height))
let width=Int(rect.width*scale), height=Int(rect.height*scale)
guard let context=CGContext(data:nil,width:width,height:height,bitsPerComponent:8,bytesPerRow:0,space:CGColorSpaceCreateDeviceRGB(),bitmapInfo:CGImageAlphaInfo.premultipliedLast.rawValue) else { fail("Renderização falhou.") }
context.setFillColor(NSColor.white.cgColor); context.fill(CGRect(x:0,y:0,width:width,height:height))
context.scaleBy(x:scale,y:scale); context.translateBy(x:-rect.minX,y:-rect.minY)
page.draw(with:.mediaBox,to:context)
guard let image=context.makeImage() else { fail("Imagem inválida.") }
if CommandLine.arguments.count==4 {
 let bitmap=NSBitmapImageRep(cgImage:image)
 try bitmap.representation(using:.png,properties:[:])!.write(to:URL(fileURLWithPath:CommandLine.arguments[3]))
 exit(0)
}
let request=VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = false
let languages = try request.supportedRecognitionLanguages()
request.recognitionLanguages = ["pt-BR","pt-PT","en-US"].filter { languages.contains($0) }
try VNImageRequestHandler(cgImage:image,options:[:]).perform([request])
let observations=(request.results ?? []).sorted {
 if abs($0.boundingBox.midY - $1.boundingBox.midY)>0.008 { return $0.boundingBox.midY > $1.boundingBox.midY }
 return $0.boundingBox.minX < $1.boundingBox.minX
}
var lines:[String]=[]
var current=""
var y:CGFloat = -1
for item in observations {
 guard let candidate=item.topCandidates(1).first else { continue }
 if y>=0 && abs(item.boundingBox.midY-y)>0.008 { lines.append(current);current="" }
 current += (current.isEmpty ? "" : "    ") + candidate.string
 y=item.boundingBox.midY
}
if !current.isEmpty { lines.append(current) }
let result:[String:Any] = ["text":lines.joined(separator:"\n")]
FileHandle.standardOutput.write(try JSONSerialization.data(withJSONObject:result))
