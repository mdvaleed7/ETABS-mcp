// Extract CHM file using Windows ITS COM object
using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;

class ChmExtractor
{
    [DllImport("itss.dll", CharSet = CharSet.Unicode)]
    static extern int DllGetClassObject(ref Guid clsid, ref Guid iid, out IntPtr ppv);
    
    static void Main(string[] args)
    {
        string chmPath = @"c:\Users\mdval\Desktop\etaps mcp\CSI API ETABS v1.chm";
        string outDir = @"c:\Users\mdval\Desktop\etaps mcp\extracted_docs";
        
        // Use the ITStorage COM interface
        var type = Type.GetTypeFromProgID("ITStorage");
        if (type == null)
        {
            Console.WriteLine("ITStorage COM object not available");
            return;
        }
        
        dynamic storage = Activator.CreateInstance(type);
        Console.WriteLine("ITStorage created successfully");
    }
}
