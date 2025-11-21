//+------------------------------------------------------------------+
//| Panel de Botones Comprar / Vender / Cerrar (solo interfaz)      |
//| Pasos 1, 2 y 3 (sin lógica de trading)                          |
//+------------------------------------------------------------------+
#property strict
#include "..\\Libraries\\LibreriaTriggerOI.mq4"

//--- Nombres de los botones
#define BTN_BUY    "btn_buy"
#define BTN_SELL   "btn_sell"
#define BTN_CLOSE  "btn_close"

//--- Colores activos/inactivos
#define CLR_BUY_ACTIVE    clrGreen      // botón Comprar activo
#define CLR_BUY_INACTIVE  clrDarkGreen  // botón Comprar inactivo

#define CLR_SELL_ACTIVE   clrRed        // botón Vender activo
#define CLR_SELL_INACTIVE clrMaroon     // botón Vender inactivo

#define CLR_CLOSE_ACTIVE   clrDarkOrange // botón Cerrar activo (naranja oscuro)
#define CLR_CLOSE_INACTIVE clrDarkOrange // botón Cerrar inactivo (mismo fondo, texto gris)

//--- Estados lógicos de los botones
bool gBuyEnabled   = true;
bool gSellEnabled  = true;
bool gCloseEnabled = false;

//Estado actual direccion
int DireccionActual = DIR_NODIR;
int DireccionNueva = DIR_NODIR;
bool PrimeraIteracion = false;

//+------------------------------------------------------------------+
//| Función auxiliar: crear un botón en el chart                     |
//+------------------------------------------------------------------+
bool CreateButton(string name,
                  string text,
                  int xDistance,
                  int yDistance,
                  int xSize,
                  int ySize,
                  color backColor)
{
   // Si ya existe, lo borramos primero
   if(ObjectFind(0,name) >= 0)
      ObjectDelete(0,name);

   if(!ObjectCreate(0, name, OBJ_BUTTON, 0, 0, 0))
      return(false);

   ObjectSetInteger(0, name, OBJPROP_CORNER,   CORNER_LEFT_UPPER);
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, xDistance);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, yDistance);
   ObjectSetInteger(0, name, OBJPROP_XSIZE,     xSize);
   ObjectSetInteger(0, name, OBJPROP_YSIZE,     ySize);

   ObjectSetString (0, name, OBJPROP_TEXT,  text);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clrWhite);        // color del texto
   ObjectSetInteger(0, name, OBJPROP_BGCOLOR, backColor);     // color de fondo
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, 10);
   ObjectSetString (0, name, OBJPROP_FONT, "Arial");

   ObjectSetInteger(0, name, OBJPROP_BACK,        true);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE,  false);
   ObjectSetInteger(0, name, OBJPROP_SELECTED,    false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN,      false);
   ObjectSetInteger(0, name, OBJPROP_STATE,       false);

   return(true);
}

//+------------------------------------------------------------------+
//| Función auxiliar: aplicar estilo según si el botón está activo   |
//+------------------------------------------------------------------+
void SetButtonEnabled(string name,
                      bool enabled,
                      color activeColor,
                      color inactiveColor)
{
   if(ObjectFind(0, name) < 0)
      return;

   // Fondo: color vivo si está activo, apagado si no
   ObjectSetInteger(0, name, OBJPROP_BGCOLOR,
                    enabled ? activeColor : inactiveColor);

   // Texto: blanco si activo, gris si desactivado
   ObjectSetInteger(0, name, OBJPROP_COLOR,
                    enabled ? (color)clrWhite : (color)clrSilver);

   // Aseguramos que no quede en "modo pulsado"
   ObjectSetInteger(0, name, OBJPROP_STATE, false);
}

//+------------------------------------------------------------------+
//| Actualiza todos los botones según los flags globales             |
//+------------------------------------------------------------------+
void UpdateAllButtons()
{
   SetButtonEnabled(BTN_BUY,   gBuyEnabled,   CLR_BUY_ACTIVE,   CLR_BUY_INACTIVE);
   SetButtonEnabled(BTN_SELL,  gSellEnabled,  CLR_SELL_ACTIVE,  CLR_SELL_INACTIVE);
   SetButtonEnabled(BTN_CLOSE, gCloseEnabled, CLR_CLOSE_ACTIVE, CLR_CLOSE_INACTIVE);
}

//+------------------------------------------------------------------+
//| OnInit: crear botones y estado inicial                           |
//+------------------------------------------------------------------+
int OnInit()
{
   // Estado inicial
   gBuyEnabled   = true;
   gSellEnabled  = true;
   gCloseEnabled = false;

   // Crear botones (posición simple en la parte superior izquierda)
   int x0 = 10;
   int y0 = 20;
   int w  = 90;
   int h  = 20;

   CreateButton(BTN_BUY,   "Comprar", x0,          y0, w, h, CLR_BUY_ACTIVE);
   CreateButton(BTN_SELL,  "Vender",  x0 + 100,    y0, w, h, CLR_SELL_ACTIVE);
   CreateButton(BTN_CLOSE, "Cerrar",  x0 + 200,    y0, w, h, CLR_CLOSE_ACTIVE);

   // Ajustar colores según estados (Cerrar empezará apagado)
   UpdateAllButtons();

   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| OnDeinit: limpiar los objetos del chart                          |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   ObjectDelete(0, BTN_BUY);
   ObjectDelete(0, BTN_SELL);
   ObjectDelete(0, BTN_CLOSE);
}

//+------------------------------------------------------------------+
//| OnTick: de momento vacío (sin lógica de trading)                 |
//+------------------------------------------------------------------+
void OnTick()
{

   if (LecturaMercado)
   { 
      Traza1 = "";
      if (Log == 1) Trazas(" LecturaMercado-->...", Traza1);      
      if (Log == 1) Trazas(" LecturaMercado--> Direccion Actual: " + IntegerToString(DireccionActual), Traza1);      
      if (Log == 1) Traza2 = "";
      
      int Direccion = CambioDireccion();

      if (Direccion == DIR_LARGOS)
      {
         Traza0 = "";

         if (Comprar() > 0)
         {
            LecturaMercado = false;
            SalidaMercado = true;
         }
      }
      else if (Direccion == DIR_CORTOS)
      {
         Traza0 = "";

         if (Vender() > 0)
         {
            LecturaMercado = false;
            SalidaMercado = true;
         }
      }   
   }
   else if (SalidaMercado)
   {
      if (Log == 1) Traza3 = "";
      if (Log == 1) Trazas(" SalidaMercado", Traza3); 
           
      if (SalidaporTPSL(commentSalida) == 0)
      {
         if (Log == 1) Trazas(" TP ejecutado", Traza3); 
         LecturaMercado = true;
         SalidaMercado = false; 
         // Meter datos de pipos ganados y ganancias obtenidas...        
         if (Log == 1) Trazas(" Datos resumen de la operación: ", Traza3); 

      }
   }
   
   Comment("\n", "\n", "\n", "\n", Traza0, 
   "\n--------------------------------", 
   Traza1, 
   "\n--------------------------------", 
   Traza2,
   "\n--------------------------------",
   Traza3,        
   "\n--------------------------------",
   Traza4);         

}

//+------------------------------------------------------------------+
//| OnChartEvent: detectar clics en los botones                      |
//+------------------------------------------------------------------+
void OnChartEvent(const int id,
                  const long   &lparam,
                  const double &dparam,
                  const string &sparam)
{
   if(id != CHARTEVENT_OBJECT_CLICK)
      return;

   string name = sparam;

   // Botón COMPRAR
   if(name == BTN_BUY && gBuyEnabled)
   {
      Comprar();      
   }

   // Botón VENDER
   else if(name == BTN_SELL && gSellEnabled)
   {
      Vender();
   }

   // Botón CERRAR
   else if(name == BTN_CLOSE && gCloseEnabled)
   {
      Cerrar();
   }
}
//+------------------------------------------------------------------+

int CambioDireccion()
{
   int iCambioDireccion = DIR_NODIR;

   ZigZagFractal(Par, PERIOD_M15, 4, 5, 3, 2);
   
   if (ZZAux[0] > ZZAux[1])
   {
      DireccionNueva = DIR_LARGOS;
      
      if (DireccionActual != DireccionNueva)
      {
         DireccionActual = DireccionNueva;
         if (Log == 1) Trazas(" Cambio Direccion --> Direccion Actual: Largos", Traza1);      
         iCambioDireccion = DIR_LARGOS;
      } 
      
      if (!PrimeraIteracion)
      {
         PrimeraIteracion = true;
         iCambioDireccion = DIR_NODIR;
         if (Log == 1) Trazas(" Cambio Direccion --> Activada Primera Iteracion", Traza0);      
      }
   }
   else if (ZZAux[0] < ZZAux[1])
   {
      DireccionNueva = DIR_CORTOS;

      if (DireccionActual != DireccionNueva)
      {
         DireccionActual = DireccionNueva;
         iCambioDireccion = DIR_CORTOS;
         if (Log == 1) Trazas(" Cambio Direccion --> Direccion Actual: Cortos", Traza1);      
      }    

      if (!PrimeraIteracion)
      {
         PrimeraIteracion = true;
         iCambioDireccion = DIR_NODIR;
         if (Log == 1) Trazas(" Cambio Direccion --> Activada Primera Iteracion", Traza0);      
      }
   }
   
   return(iCambioDireccion);
}

int Comprar()
{
   LotsForMarginPercent(0.7, numerooperaciones, miniLotes);

   commentSalida = Par;
   if (Log == 1) Trazas(" CommentSalida:" + commentSalida + " Nº Operaciones: " + IntegerToString(numerooperaciones) + " MiniLotes: " + DoubleToStr(miniLotes)  , Traza2);
   
   OperacionesAbiertas = ExecMarket(DIR_LARGOS, numerooperaciones, miniLotes, commentSalida);
   if (Log == 1) Trazas(" Operaciones Abiertas: " + IntegerToString(OperacionesAbiertas), Traza2);

   //Ejecutas orden en el mercado
   if (OperacionesAbiertas > 0)
   {
      // Al comprar, desactivamos Comprar y Vender,
      // y dejamos solo Cerrar activo.
      gBuyEnabled   = false;
      gSellEnabled  = false;
      gCloseEnabled = true;

      UpdateAllButtons();
   }
   
   return(OperacionesAbiertas);
}

int Vender()
{
   // Al vender, desactivamos Comprar y Vender,
   // y dejamos solo Cerrar activo.
   LotsForMarginPercent(0.7, numerooperaciones, miniLotes);

   commentSalida = Par;
   if (Log == 1) Trazas(" CommentSalida:" + commentSalida + " Nº Operaciones: " + IntegerToString(numerooperaciones) + " MiniLotes: " + DoubleToStr(miniLotes), Traza2);
   
   OperacionesAbiertas = ExecMarket(DIR_CORTOS, numerooperaciones, miniLotes, commentSalida);
   if (Log == 1) Trazas(" Operaciones Abiertas: " + IntegerToString(OperacionesAbiertas), Traza2);

   //Ejecutas orden en el mercado
   if (OperacionesAbiertas > 0)
   {
      gBuyEnabled   = false;
      gSellEnabled  = false;
      gCloseEnabled = true;

      UpdateAllButtons();
   }

   return(OperacionesAbiertas);

}

void Cerrar()
{
   if (CierreOrdenes(commentSalida) > 0)
   {
      if (Log == 1) Trazas(" Cerradas operaciones", Traza3);      
      // Volver al estado inicial
      gBuyEnabled   = true;
      gSellEnabled  = true;
      gCloseEnabled = false;
   
      UpdateAllButtons();
   }   
}